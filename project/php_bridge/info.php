<?php
/**
 * Optional PHP entry for coursework that requires a .php file in the stack.
 * The production app runs on Django; point users to the Django URL below.
 * Serve this folder with PHP built-in server only if needed:
 *   php -S localhost:8080 -t php_bridge
 */
$django = getenv('DJANGO_APP_URL') ?: 'http://127.0.0.1:8000/';
header('Location: ' . $django, true, 302);
exit;
