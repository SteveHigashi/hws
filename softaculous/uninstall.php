<?php
/**
 * Softaculous uninstaller for Higashi Analytics.
 * Removes the virtualenv and settings — app files are removed by Softaculous.
 */

$install_dir = getenv('SU_PHP_INSTALL_DIR') ?: rtrim($_POST['install_dir'] ?? dirname(__DIR__), '/');

// Remove virtualenv (large, not app files)
$venv = "$install_dir/.venv";
if (is_dir($venv)) {
    exec("rm -rf " . escapeshellarg($venv));
    echo "Removed virtualenv.\n";
}

// Remove generated files — leave DB intact so data survives accidental uninstall
foreach (['.htaccess'] as $f) {
    $path = "$install_dir/$f";
    if (file_exists($path)) {
        unlink($path);
    }
}

$data_dir = @file_get_contents("$install_dir/backend/.higashi_data_dir");
$data_dir = $data_dir ? trim($data_dir) : "~/.higashi/";
echo "✓ Higashi Analytics uninstalled. Your database and settings were preserved.\n";
echo "  Delete $data_dir manually if you want to remove all data.\n";
