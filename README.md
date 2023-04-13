# Remote Odoo Request Update

A convenient tool help you update one or more module(s) on remote Odoo (OpenERP) server without access Web GUI.

_Package `termcolor` is optional to support colored text in terminal_

### Usage example

Firstly, you will need create a config file, example `demo_config.json` with content:
```json
{
    "url": "http://localhost:8069",
    "db": "my_database",
    "username": "admin",
    "password": "admin",
    "modules_to_update": ["foo", "bar"]
}
```

This config tell application execute update for modules: `foo`, `bar` using target URL `http://localhost:8069` and database `my_database`

#### Run app

GUI mode will active by default if app call without params.

* **Console** mode:

  Run `app.py` with param:
 
  * `python app.py demo_config.json`
  * or you want to **overwrite** admin password, run: `python app.py demo_config.json real-password`

* **GUI** mode:
  * `python app.py`
  
    > ![](images/OdooRUR.png)

### Build execute file

* Build with `pyinstaller`: 
    ```bash
    pyinstaller --onefile --noconsole --name OdooRUR app.py
    # with icon
    # param --add-data to add resource to execute file
    pyinstaller --onefile --noconsole --name OdooRUR --icon resources\icon.ico --add-data "resources\\icon.ico;resources" app.py
    ```