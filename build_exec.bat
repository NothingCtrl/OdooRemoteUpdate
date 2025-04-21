@title Build Execute File

pyinstaller --onefile --noconsole --name OdooRUR --icon resources\icon.ico --add-data "resources\\icon.ico;resources" --add-data "resources\\success.wav;resources" --add-data "resources\\error.wav;resources" app.py