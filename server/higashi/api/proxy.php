<?php
// Reverse proxy for the Higashi dashboard at https://cloudanalyst.net/higashi/
// Forwards requests to the local FastAPI backend on 127.0.0.1:8001.
//
// The browser bundles call this as:
//   /higashi/api/proxy.php?path=/api/<endpoint>[&other=params]
//
// We strip 'path' from the query string, forward everything else, preserve
// the HTTP method, request body, and headers (including Authorization), and
// stream the response back so SSE and chunked POST endpoints work.

set_time_limit(0);
ignore_user_abort(true);
@ini_set('zlib.output_compression', '0');
@ini_set('output_buffering', '0');
@ini_set('implicit_flush', '1');
while (ob_get_level() > 0) ob_end_flush();
ob_implicit_flush(true);

$path = $_GET['path'] ?? '';
if ($path === '' || $path[0] !== '/') {
    http_response_code(400);
    echo 'Missing or invalid path';
    exit;
}

// Forward remaining query string (everything except 'path')
$qs = $_GET;
unset($qs['path']);
$qsStr = $qs ? '?' . http_build_query($qs) : '';
$url = 'http://127.0.0.1:8001' . $path . $qsStr;

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$body = file_get_contents('php://input');

// Build header list to forward (drop hop-by-hop and request-specific ones)
$headers = [];
foreach (getallheaders() as $k => $v) {
    $lower = strtolower($k);
    if (in_array($lower, ['host', 'connection', 'content-length', 'accept-encoding'])) continue;
    $headers[] = "$k: $v";
}
// Ensure JSON content type for POST/PATCH/PUT when client sent text/plain (sendBeacon quirk)
if (in_array($method, ['POST', 'PATCH', 'PUT']) && $body !== '') {
    $hasCT = false;
    foreach ($headers as $h) if (stripos($h, 'content-type:') === 0) { $hasCT = true; break; }
    if (!$hasCT) $headers[] = 'Content-Type: application/json';
}

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_HTTPHEADER     => $headers,
    CURLOPT_POSTFIELDS     => $body,
    CURLOPT_RETURNTRANSFER => false,
    CURLOPT_HEADER         => false,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_TIMEOUT        => 0,
    CURLOPT_CONNECTTIMEOUT => 5,
    CURLOPT_BUFFERSIZE     => 256,
    CURLOPT_TCP_NODELAY    => true,
    CURLOPT_HEADERFUNCTION => function ($ch, $header) {
        $trim = trim($header);
        if ($trim === '') return strlen($header);
        if (preg_match('#^HTTP/\S+ (\d+)#', $trim, $m)) {
            http_response_code((int)$m[1]);
            return strlen($header);
        }
        $lower = strtolower($trim);
        // Strip headers PHP will set itself or that break streaming
        if (strpos($lower, 'transfer-encoding:') === 0) return strlen($header);
        if (strpos($lower, 'content-length:') === 0) return strlen($header);
        if (strpos($lower, 'content-encoding:') === 0) return strlen($header);
        if (strpos($lower, 'connection:') === 0) return strlen($header);
        header($trim, false);
        return strlen($header);
    },
    CURLOPT_WRITEFUNCTION  => function ($ch, $chunk) {
        echo $chunk;
        @ob_flush();
        @flush();
        return strlen($chunk);
    },
]);

curl_exec($ch);
if (curl_errno($ch)) {
    if (!headers_sent()) {
        http_response_code(502);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'backend unreachable', 'detail' => curl_error($ch)]);
    }
}
curl_close($ch);
