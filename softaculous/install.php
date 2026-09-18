<?php
/**
 * Softaculous / Fantastico installer for Higashi Analytics.
 *
 * Runs on the target cPanel server via the control panel's installer framework.
 * Shells out to Python for venv setup and DB initialization.
 */

// ── Helpers ──────────────────────────────────────────────────────────────────

function run($cmd, &$output = null) {
    exec($cmd . ' 2>&1', $lines, $code);
    $output = implode("\n", $lines);
    return $code === 0;
}

function abort($msg) {
    echo "ERROR: $msg\n";
    exit(1);
}

function info($msg) {
    echo "$msg\n";
}

// ── Detect Python ─────────────────────────────────────────────────────────────

$python = null;
foreach (['python3.12', 'python3.11', 'python3.10', 'python3.9', 'python3'] as $bin) {
    if (run("which $bin", $out) && !empty(trim($out))) {
        $python = trim($out);
        break;
    }
}

if (!$python) {
    abort("Python 3.9+ is required but was not found on this server.\n" .
          "Please enable Python via cPanel > Setup Python App before installing.");
}

run("$python --version", $pyver);
info("Found Python: $pyver at $python");

// ── Install directory (provided by Softaculous as SU_PHP_INSTALL_DIR) ────────

$install_dir = getenv('SU_PHP_INSTALL_DIR') ?: rtrim($_POST['install_dir'] ?? dirname(__DIR__), '/');
if (!is_dir($install_dir)) {
    abort("Install directory does not exist: $install_dir");
}

$backend_dir = "$install_dir/backend";
if (!is_dir($backend_dir)) {
    abort("Backend directory not found. Ensure the Higashi files were extracted to: $install_dir");
}

info("Installing to: $install_dir");

// ── Create virtualenv ─────────────────────────────────────────────────────────

$venv = "$install_dir/.venv";
if (!is_dir($venv)) {
    info("Creating Python virtual environment...");
    if (!run("$python -m venv $venv", $out)) {
        abort("Failed to create virtualenv: $out");
    }
}

$pip = "$venv/bin/pip";
$python_venv = "$venv/bin/python";

// ── Install dependencies ──────────────────────────────────────────────────────

info("Installing Python dependencies (this may take a minute)...");
$req = "$backend_dir/requirements-minimal.txt";
if (!run("$pip install --quiet -r $req", $out)) {
    abort("pip install failed: $out");
}

// ── Data directory (outside the web root) ───────────────────────────────────
// settings.env holds SECRET_KEY and AI keys; higashi.db holds everything else.
// Both used to sit in $install_dir, where the web server could hand them out.

$home = getenv('HOME');
if (!$home && function_exists('posix_getpwuid')) {
    $pw = posix_getpwuid(posix_geteuid());
    $home = $pw['dir'] ?? '';
}
if (!$home || !is_dir($home)) {
    abort("Could not find the account's home directory to store settings outside the website.");
}
$data_dir = rtrim($home, '/') . '/.higashi/' . substr(sha1($install_dir), 0, 12);
if (!is_dir($data_dir) && !mkdir($data_dir, 0700, true)) {
    abort("Could not create data directory: $data_dir");
}
chmod(dirname($data_dir), 0700);
chmod($data_dir, 0700);

$settings_file = "$data_dir/settings.env";
$db_path       = "$data_dir/higashi.db";

// Upgrades: move files left in the web root by older installers.
foreach ([["$install_dir/settings.env", $settings_file], ["$backend_dir/settings.env", $settings_file],
          ["$install_dir/higashi.db", $db_path], ["$backend_dir/higashi.db", $db_path]] as [$old, $new]) {
    if (file_exists($old) && !file_exists($new)) {
        if (!rename($old, $new)) {
            abort("Could not move $old out of the website folder. Move it to $new by hand and re-run.");
        }
        info("Moved " . basename($old) . " out of the website folder.");
    }
}
if (file_exists($settings_file)) {
    $env = file_get_contents($settings_file);
    $env = preg_replace('/^DATABASE_URL=.*$/m', "DATABASE_URL=sqlite+aiosqlite:///$db_path", $env);
    $env = preg_replace('/^HIGASHI_ENV_PATH=.*$/m', "HIGASHI_ENV_PATH=$settings_file", $env);
    file_put_contents($settings_file, $env);
}

// Tell passenger_wsgi.py where the data lives (a path, not a secret).
file_put_contents("$backend_dir/.higashi_data_dir", $data_dir);

// ── Write settings.env ───────────────────────────────────────────────────────

if (!file_exists($settings_file)) {
    $secret_key = bin2hex(random_bytes(32));
    $env_content = <<<ENV
SECRET_KEY=$secret_key
DATABASE_URL=sqlite+aiosqlite:///$db_path
HIGASHI_ENV_PATH=$settings_file
ENV;
    file_put_contents($settings_file, $env_content);
    info("Created settings.env");
}
chmod($settings_file, 0600);
if (file_exists($db_path)) {
    chmod($db_path, 0600);
}

// ── Run database migrations ───────────────────────────────────────────────────

info("Running database migrations...");
$alembic = "$venv/bin/alembic";
if (!run("cd $backend_dir && HIGASHI_ENV_PATH=$settings_file $alembic upgrade head", $out)) {
    abort("Database migration failed: $out");
}

// ── Configure Passenger (.htaccess) ──────────────────────────────────────────

$htaccess = "$install_dir/.htaccess";

// Refuse to serve anything that isn't a public asset, even if a secret file
// ends up in the web root again. Added to existing .htaccess files on upgrade.
$guard_marker = "# BEGIN Higashi file guard";
$guard = <<<GUARD
$guard_marker
<FilesMatch "(^\.|\.(env|db|sqlite|sqlite3|db-journal|db-wal|db-shm|pem|key|log|bak|ini|cfg|toml)$)">
    <IfModule mod_authz_core.c>
        Require all denied
    </IfModule>
    <IfModule !mod_authz_core.c>
        Order allow,deny
        Deny from all
    </IfModule>
</FilesMatch>
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteRule (^|/)(\.venv|\.git|backend|__pycache__|migrations)(/|$) - [F,L]
    # Source files that really exist on disk. (Not a FilesMatch: the Passenger
    # rule below rewrites every app request to passenger_wsgi.py.)
    RewriteCond %{REQUEST_FILENAME} -f
    RewriteRule \.(py|pyc)$ - [F,L]
</IfModule>
# END Higashi file guard

GUARD;
if (file_exists($htaccess) && strpos(file_get_contents($htaccess), $guard_marker) === false) {
    file_put_contents($htaccess, $guard . file_get_contents($htaccess));
    info("Added file guard to existing .htaccess");
}

if (!file_exists($htaccess)) {
    $htaccess_content = $guard . <<<HTACCESS
PassengerEnabled On
PassengerAppRoot $install_dir/backend
PassengerStartupFile passenger_wsgi.py
PassengerPython $python_venv
PassengerAppType wsgi

# Forward everything to the Python app except existing static files
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [QSA,L]
HTACCESS;
    file_put_contents($htaccess, $htaccess_content);
    info("Created .htaccess for Passenger");
}

// ── Done ──────────────────────────────────────────────────────────────────────

$setup_url = (isset($_SERVER['HTTPS']) ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? 'your-domain.com') . '/setup';

info("\n✓ Higashi Analytics installed successfully.");
info("  Open your site and complete setup at: $setup_url");
info("  Admin email and password are set during first-run setup in the browser.");
