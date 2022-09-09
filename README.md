# Remote Odoo Request Update

Request remote server Odoo run update on specific modules with XMLRPC call

Package `termcolor` is optional to support colored text in terminal

**Usage example:**

Create a config file, name: `demo_config.json`, file content:
```json
{
    "url": "http://localhost:8069",
    "db": "my_database",
    "username": "admin",
    "password": "admin",
    "modules_to_update": ["foo", "bar"]
}
```

Run update request: `python app.py demo_config.json`, this will run update for module `foo`, `bar`
