<?php
// CORS for the cross-origin tracker (viabandwidth.com → cloudanalyst.net).
// The origin is echoed from an explicit list, never "*": the tracker posts
// with navigator.sendBeacon, which always sends credentials, and a browser
// refuses a wildcard on a credentialed request. With "*" every cross-site
// pageview and behaviour batch was blocked at preflight (found 2026-09-18).
$allowed = [
    "https://viabandwidth.com", "https://www.viabandwidth.com",
    "https://gpu.viabandwidth.com", "https://colo.viabandwidth.com",
    "https://carrier.viabandwidth.com", "https://bandwidth.viabandwidth.com",
    "https://dc.viabandwidth.com", "https://ip.viabandwidth.com",
    "https://msp.viabandwidth.com",
];
$origin = $_SERVER["HTTP_ORIGIN"] ?? "";
if (in_array($origin, $allowed, true)) {
    header("Access-Control-Allow-Origin: " . $origin);
    header("Access-Control-Allow-Credentials: true");
    header("Vary: Origin");
}
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
if ($_SERVER["REQUEST_METHOD"] === "OPTIONS") { http_response_code(204); exit; }

$path = preg_replace("/\.php$/", "", $_SERVER["SCRIPT_NAME"]);
$url  = "http://127.0.0.1:8001" . $path;

$body    = file_get_contents("php://input");
$headers = ["Content-Type: application/json"];
foreach (getallheaders() as $k => $v) {
    $lower = strtolower($k);
    if (in_array($lower, ["host", "connection", "content-length", "content-type", "origin"])) continue;
    $headers[] = "$k: $v";
}

$ctx = stream_context_create(["http" => [
    "method"        => "POST",
    "header"        => implode("\r\n", $headers),
    "content"       => $body,
    "ignore_errors" => true,
    "timeout"       => 10,
]]);

$response = @file_get_contents($url, false, $ctx);
foreach ($http_response_header ?? [] as $h) {
    if (preg_match("#^HTTP/\S+ (\d+)#", $h, $m)) { http_response_code((int)$m[1]); continue; }
    if (stripos($h, "transfer-encoding") === 0) continue;
    if (stripos($h, "access-control") === 0) continue;
    header($h, false);
}
echo $response ?: "";
