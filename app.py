"""
Run module update on remove server
"""
import os
import time
import json
import sys
import datetime
import xmlrpc.client

base_dir = os.path.dirname(os.path.abspath(__file__))

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

def log_to_file(log_text: str):
    log_dir = os.path.join(base_dir, 'logs')
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    log_file = os.path.join(log_dir, os.path.basename(sys.argv[1]).replace('.json', '') + "_execute_log_" + str(int(time.time())) + '.txt')
    with open(log_file, 'w+') as f_log:
        f_log.write(log_text.replace('\\\\n', "\n").replace('\\n', "\n"))
    return log_file

def run_update(cf: Config):
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(cf.url))
    uid = common.authenticate(cf.db, cf.username, cf.password, {})
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(cf.url))
    model_name = 'ir.module.module'
    update_method = 'button_immediate_upgrade'

    total_update = len(cf.modules_to_update)
    print("\n", "=" * 70, sep='')
    print(f"- ERP server: {cf.url if not color_allow else colored(cf.url, 'green')}")
    print(f"- Database: {cf.db if not color_allow else colored(cf.db, 'green')}")
    print("- Total module to update: {}, module technical name list:{}".format(total_update, "".join(f"\n    + {item}" for item in cf.modules_to_update)))
    print("=" * 70, "\n", sep='')
    input("Press Enter to continue...")
    print("Running (current time is: ", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ")...\n", sep='')
    
    count = 0
    for tech_name in cf.modules_to_update:
        count += 1
        try:
            ids = models.execute_kw(cf.db, uid, cf.password, model_name, "search", [[('name', '=', tech_name.strip())]])
        except xmlrpc.client.Fault as e:
            if 'Access denied' in str(e):
                print("- 'Access denied' please check user account and login password!")
            else:
                print("- Error: {}".format(e))
            return
        if ids:
            start_time = time.time()
            log_file_path = None
            try:
                result = models.execute_kw(cf.db, uid, cf.password, model_name, update_method, [ids])
            except xmlrpc.client.Fault as e:
                log_file_path = log_to_file(e.__str__())
                result = None
            if type(result) is dict and (('tag' in result and result['tag'] == 'reload') or ('url' in result and result['url'] == '/web')):
                # success, server response: client reload or redirect to home page
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
                if log_file_path:
                    print("    - Log file: {}".format(log_file_path))
        else:
            if not color_allow:
                print("- [{}/{}] Update module [{}] --- FAILED, module is not found!".format(count, total_update, tech_name))
            else:
                print("- [{}/{}] Update module [{}] --- {}, module is not found!".format(count, total_update, tech_name, colored('FAILED', 'red')))
    
if __name__ == "__main__":
    if len(sys.argv) <= 1:
        if not color_allow:
            print("Required call with config file path, ex: 'python app.py /path/to/config.json' or to overwrite "
                  "password: 'python app.py /path/to/config.json my-password'")
        else:
            print("Required call with config file path, ex: " + colored('python app.py /path/to/config.json', 'green')
                  + " or to overwrite password: " + colored('python app.py /path/to/config.json ', 'green') + colored('my-password', 'red'))
    else:
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], "r") as f:
                config = json.load(f)
                erp_config = Config(**config)
                if len(sys.argv) == 3:
                    erp_config.password = sys.argv[2]
                run_update(erp_config)
        else:
            if not color_allow:
                print("The config file: {} is not found!".format(sys.argv[1]))
            else:
                print("The config file: {} is not found!".format(colored(sys.argv[1], 'red')))
    