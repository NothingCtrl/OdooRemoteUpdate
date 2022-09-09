"""
Run module update on remove server
"""
import os
import time
import json
import sys
import xmlrpc.client

color_allow = True
try:
    from termcolor import colored
    if os.name == 'nt':
        os.system('color')
except ImportError:
    color_allow = False

class Config:
    url: str
    db: str
    username: str = "admin"
    password: str
    modules_to_update: list = []
    
    def __init__(self, url: str, db: str, password: str, modules_to_update: list, username: str = "admin"):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.modules_to_update = modules_to_update

def run_update(cf: Config):
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(cf.url))
    uid = common.authenticate(cf.db, cf.username, cf.password, {})      # <- use it later
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(cf.url))     # <- user it later
    model_name = 'ir.module.module'
    update_method = 'button_immediate_upgrade'

    total_update = len(cf.modules_to_update)
    print("=== Total module to update: {}, list: {} ===".format(total_update, cf.modules_to_update))
    count = 0
    for tech_name in cf.modules_to_update:
        count += 1
        ids = models.execute_kw(cf.db, uid, cf.password, model_name, "search", [[('name', '=', tech_name.strip())]])
        if ids:
            start_time = time.time()
            result = models.execute_kw(cf.db, uid, cf.password, model_name, update_method, [ids])
            if type(result) is dict and 'tag' in result and result['tag'] == 'reload':
                end_time = time.time()
                if not color_allow:
                    print("- [{}/{}] Update module [{}] --- OK, run-time: {:.2f} seconds".format(count, total_update,
                                                                                                 tech_name, end_time - start_time))
                else:
                    print("- [{}/{}] Update module [{}] --- {}, run-time: {:.2f} seconds".format(count, total_update,
                                                                                                 tech_name, colored('OK', 'green'), end_time - start_time))
            else:
                if not color_allow:
                    print("- [{}/{}] Update module [{}] --- FAILED".format(count, total_update, tech_name), "RESPONSE: {}".format(result))
                else:
                    print("- [{}/{}] Update module [{}] --- {}".format(count, total_update, tech_name, colored('FAILED', 'red')), "RESPONSE: {}".format(result))
        else:
            if not color_allow:
                print("- [{}/{}] Update module [{}] --- FAILED, module is not found!".format(count, total_update, tech_name))
            else:
                print("- [{}/{}] Update module [{}] --- {}, module is not found!".format(count, total_update, tech_name, colored('FAILED', 'red')))
    
if __name__ == "__main__":
    if len(sys.argv) == 1:
        if not color_allow:
            print("Required call with config file path, ex: python app.py /path/to/config.json")
        else:
            print("Required call with config file path, ex: " + colored('python app.py /path/to/config.json', 'green'))
    else:
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], "r") as f:
                config = json.load(f)
                run_update(Config(**config))
        else:
            if not color_allow:
                print("The config file: {} is not found!".format(sys.argv[1]))
            else:
                print("The config file: {} is not found!".format(colored(sys.argv[1], 'red')))
    