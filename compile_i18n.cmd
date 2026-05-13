@echo off
REM Compile internationalization files for al-script
echo Compiling i18n translation files...
echo.
echo Translation files are located in: module/i18n/
echo.
echo To add a new language:
echo   1. Copy module/i18n/en.json to module/i18n/<lang_code>.json
echo   2. Translate the values in the new file
echo   3. Restart the application
echo.
echo Available translations:
dir /b module\i18n\*.json
echo.
echo Done.
