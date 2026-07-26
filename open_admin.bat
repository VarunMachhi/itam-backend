@echo off
REM Opens the admin dashboard directly via Windows' "start" command instead
REM of the browser address bar. Chrome's "HTTPS Upgrades" feature only
REM triggers on addresses you TYPE into the omnibox -- a URL launched this
REM way is passed straight through, so it can't get silently rewritten to
REM https:// (which is what was causing ERR_SSL_PROTOCOL_ERROR: the dev
REM server only speaks plain HTTP, but Chrome kept trying HTTPS anyway).
start http://127.0.0.1:8000/admin/
