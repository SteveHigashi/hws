<?php
// Reverse proxy: forwards /analytics/api/* → http://127.0.0.1:8001/api/*
$backend = 'http://127.0.0.1:8001';

// Path comes from RewriteRule — strip leading slash if present
$path = '/' . ltrim($_GET['path'] ?? 'api/health', '/');

// Forward query string minus our internal 'path' param.
// If the inner path already contains a query string (e.g. ?days=30 was
// encoded into the 'path' param), join with '&' instead of '?' so we
// don't produce a malformed URL like /overview?days=30?site_id=...
$query = $_GET;
unset($query['path']);
if ($query) {
    $sep = strpos($path, '?') === false ? '?' : '&';
    $path .= $sep . http_build_query($query);
}

$url = $backend . $path;

// Copy request headers (except Host)
$headers = [];
foreach (getallheaders() as $k => $v) {
    if (strtolower($k) === 'host') continue;
    $headers[] = "$k: $v";
}

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_TIMEOUT        => 30,
    CURLOPT_HTTPHEADER     => $headers,
    CURLOPT_CUSTOMREQUEST  => $_SERVER['REQUEST_METHOD'],
    CURLOPT_HEADER         => true,
]);

// Forward request body for POST/PATCH/PUT
$method = strtoupper($_SERVER['REQUEST_METHOD']);
if (in_array($method, ['POST', 'PATCH', 'PUT'])) {
    $body = file_get_contents('php://input');
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

$response   = curl_exec($ch);
$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$httpCode   = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlErr    = curl_errno($ch) ? curl_error($ch) : '';
curl_close($ch);

// A backend that is down or too slow must not look like an empty 200 to the dashboard.
if ($response === false || $httpCode === 0) {
    http_response_code(502);
    header('Content-Type: application/json');
    echo json_encode(['detail' => 'Higashi backend did not answer: ' . ($curlErr ?: 'no response')]);
    exit;
}

// Split headers from body
$rawHeaders = substr($response, 0, $headerSize);
$body       = substr($response, $headerSize);

// Forward response headers (skip Transfer-Encoding which curl already decoded)
foreach (explode("\r\n", $rawHeaders) as $line) {
    if (preg_match('/^(HTTP\/|Transfer-Encoding:|Connection:)/i', $line)) continue;
    if (trim($line)) header($line);
}

http_response_code($httpCode);
echo $body;
