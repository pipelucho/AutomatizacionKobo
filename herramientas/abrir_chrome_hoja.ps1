# Abre un Chrome aparte (perfil propio, solo para la hoja) al que el bot se puede conectar.
# La primera vez inicia sesion en Google a mano en esa ventana; la sesion queda guardada en el perfil.
# Mientras esta ventana este abierta, programas de este computador pueden controlarla:
# usala solo para la hoja y cierrala al terminar.
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$perfil = Join-Path $env:LOCALAPPDATA "TumacoChrome"
$hoja = "https://docs.google.com/spreadsheets/d/1sKzEkMpefgbGclUG54sgASOmp6Dr7EJR/edit#gid=1042612756"
Start-Process $chrome -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=`"$perfil`"", $hoja
