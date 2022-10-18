"""
Run module update on remove server
"""
import os
import time
import json
import sys
import datetime
import threading
import xmlrpc.client
import PySimpleGUI as sg

base_dir = os.path.dirname(os.path.abspath(__file__))

INIT_STATE_EVENT = '--INIT-STATE--'
color_allow = True
gui_status_text = ''
event, values, is_cancel, is_running, is_exit = INIT_STATE_EVENT, {}, False, False, False

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

def run_update(cf: Config, output_handler: callable = None, is_gui: bool = False):
    global color_allow
    if is_gui:
        color_allow = False
    def output(msg: str, sep="\n"):
        if not callable(output_handler):
            print(msg, sep=sep)
        else:
            output_handler(msg)
    if is_gui:
        output(f"Running (current time is: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})...\n", sep='')
    output("Connecting remote server...")
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(cf.url))
    try:
        uid = common.authenticate(cf.db, cf.username, cf.password, {})
        output("Remote server connected")
    except ConnectionRefusedError as e:
        output(str(e))
        return
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(cf.url))
    model_name = 'ir.module.module'
    update_method = 'button_immediate_upgrade'
    total_update = len(cf.modules_to_update)

    if not is_gui:
        print("\n", "=" * 70, sep='')
    output(f"- ERP server: {cf.url if not color_allow else colored(cf.url, 'green')}")
    output(f"- Database: {cf.db if not color_allow else colored(cf.db, 'green')}")
    output("- Total module to update: {}, module technical name list:{}".format(total_update, "".join(f"\n    + {item}" for item in cf.modules_to_update)))
    if not is_gui:
        print("=" * 70, "\n", sep='')
        input("Press Enter to continue...")
    if not is_gui:
        output(f"Running (current time is: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})...\n", sep='')
    
    count = 0
    for tech_name in cf.modules_to_update:
        count += 1
        try:
            output(f"- Requesting update module: {tech_name}...")
            ids = models.execute_kw(cf.db, uid, cf.password, model_name, "search", [[('name', '=', tech_name.strip())]])
        except xmlrpc.client.Fault as e:
            if 'Access denied' in str(e):
                output("- 'Access denied' please check user account and login password!")
            else:
                output("- Error: {}".format(e))
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
                    output("- [{}/{}] Update module [{}] --- OK, run-time: {:.2f} seconds".format(count, total_update,
                                                                                                 tech_name, end_time - start_time))
                else:
                    output("- [{}/{}] Update module [{}] --- {}, run-time: {:.2f} seconds".format(count, total_update,
                                                                                                 tech_name, colored('OK', 'green'), end_time - start_time))
            else:
                if not color_allow:
                    output("- [{}/{}] Update module [{}] --- FAILED".format(count, total_update, tech_name), "RESPONSE: {}".format(result))
                else:
                    output("- [{}/{}] Update module [{}] --- {}".format(count, total_update, tech_name, colored('FAILED', 'red')), "RESPONSE: {}".format(result))
                if log_file_path:
                    output("    - Log file: {}".format(log_file_path))
        else:
            if not color_allow:
                output("- [{}/{}] Update module [{}] --- FAILED, module is not found!".format(count, total_update, tech_name))
            else:
                output("- [{}/{}] Update module [{}] --- {}, module is not found!".format(count, total_update, tech_name, colored('FAILED', 'red')))

def console_mode():

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

def gui_mode():
    config_update = [
        [
            sg.Text("Config file", size=(15,1)),
            sg.Input(size=(25,1), key='-CF-FILE-'),
            sg.FileBrowse(),
        ],
        [
            sg.Text("Modules to update", size=(15,1)),
            sg.Multiline(size=(25, 4), key='-MODULES-')
        ],
        [
            sg.Text('Admin password', size=(15,1)),
            sg.Input(size=(25, 1), password_char='*', key='-ADMIN-PWD-')
        ],
        [
            sg.Text('Waiting time (sec)', size=(15, 1)),
            sg.OptionMenu(size=(20, 1),
                          values=(0, 30, 60, 120, 180, 300, 600, 900, 1800, 3600), default_value=0, key='-WAITING-TIME-')
        ],
        [
            sg.Button("Run now", enable_events=True, key='-BTN-RUN-'),
            sg.Button("Cancel", enable_events=True, key='-BTN-CANCEL-')
        ]
    ]
    log_status = [
        [
            sg.Text("Status"),
            sg.Multiline(size=(60, 10), key='-STATUS-', disabled=True, autoscroll=True, auto_refresh=True)
        ]
    ]
    layout = [
        [
            sg.Column(config_update),
            sg.VSeparator(),
            sg.Column(log_status)
        ]
    ]
    # sg.ChangeLookAndFeel('Dark')  # dark mode
    window = sg.Window(title="Odoo Remote Update Request", layout=layout,
                       margins=(15, 15))

    def update_status(text: str, clear: bool = False):
        global gui_status_text
        if not clear:
            gui_status_text += f"{text}\n"
        else:
            gui_status_text = f"{text}\n"
        window['-STATUS-'].update(gui_status_text)
        # window.Refresh()

    def read_event():
        global event, values, is_cancel, is_running, is_exit
        while True:
            event, values = window.read()
            if event == '-BTN-CANCEL-' and is_running:
                is_cancel = True
            if event == sg.WIN_CLOSED:
                is_exit = True
                break

    th_read_event = threading.Thread(target=read_event, daemon=True)
    th_read_event.start()

    while True:
        global event, values, is_cancel, is_running, is_exit
        # event, values = window.read()
        # if event == sg.WIN_CLOSED:
        #     break
        time.sleep(.001)
        if is_exit:
            break
        if event == '-BTN-RUN-':
            if not is_running:
                is_running = True
            else:
                return
            config_file = values['-CF-FILE-']
            modules = values['-MODULES-']
            admin_pwd = values['-ADMIN-PWD-']
            waiting_time = values['-WAITING-TIME-']
            waiting_time = int(waiting_time) if waiting_time else 0
            if config_file and modules:
                if os.path.isfile(config_file):
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                        erp_config = Config(**config)
                        erp_config.modules_to_update = modules.splitlines()
                    if admin_pwd:
                        erp_config.password = admin_pwd
                if waiting_time:
                    update_status(f"Wait for {waiting_time} seconds...")
                    i = 0
                    while i < waiting_time and not is_cancel:
                        i += 1
                        time.sleep(1)
                        window.refresh()
                        if not i % 5:
                            update_status(f"Time wait remain: {waiting_time - i} seconds...")
                if is_cancel:
                    update_status('Cancel...')
                    is_cancel = False
                else:
                    update_status('=== Start update request... ===', clear=True)
                    run_update(erp_config, update_status, True)
                    update_status("=== End ===")
            else:
                if not config_file:
                    update_status('Please select a config file...', clear=True)
                elif not modules:
                    update_status('Please input modules name, each on one line', clear=True)
            is_running = False
        if event != sg.WIN_CLOSED:
            event = INIT_STATE_EVENT

if __name__ == "__main__":
    # console_mode()
    gui_mode()
    