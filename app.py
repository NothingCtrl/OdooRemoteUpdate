"""
Run module update on remove server
"""
import os
import time
import json
import sys
import datetime
import threading
import traceback
import xmlrpc.client
from xmlrpc.client import Transport
from http import client
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


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class Config:
    url: str
    db: str
    username: str = "admin"
    password: str
    modules_to_update: list = []
    language_to_update: str = ""

    def __init__(self, url: str, db: str, password: str, modules_to_update: list, username: str = "admin"):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.modules_to_update = modules_to_update
        self.language_to_update = ""


def log_to_file(log_text: str, suffix="_execute_log_"):
    log_dir = os.path.join(base_dir, 'logs')
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    log_file = os.path.join(log_dir, os.path.basename(sys.argv[1]).replace('.json', '') + suffix + str(int(time.time())) + '.txt')
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
            output_handler(msg, sep=sep)

    # ref: https://stackoverflow.com/a/2426293/2533787
    class TimeoutTransport(Transport):
        timeout = 10.0

        def set_timeout(self, timeout):
            self.timeout = timeout

        def make_connection(self, host):
            h = client.HTTPConnection(host, timeout=self.timeout)
            return h

    def xlmrpc_login(allow_none=False):
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(cf.url), transport=t)
        _version = common.version()['server_version']
        try:
            _uid = common.authenticate(cf.db, cf.username, cf.password, {})
            output("connected!")
            output(f"- Remote server version: {_version}")
        except ConnectionRefusedError as e:
            output("error!\n" + str(e))
            return
        _models = xmlrpc.client.ServerProxy(f'{cf.url}/xmlrpc/2/object', allow_none=allow_none)
        return _models, _uid, _version

    output(f"- ERP server: {cf.url if not color_allow else colored(cf.url, 'green')}")
    output(f"- Database: {cf.db if not color_allow else colored(cf.db, 'green')}")

    if is_gui:
        output(f"- Time now: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    output("- Connecting remote server...", sep=" ")
    t = TimeoutTransport()
    t.set_timeout(15 * 60)
    models, uid, remote_odoo_version = xlmrpc_login()
    model_name = 'ir.module.module'
    update_method = 'button_immediate_upgrade'
    total_update = len(cf.modules_to_update)

    if not is_gui:
        print("\n", "=" * 70, sep='')
    if cf.modules_to_update:
        output("- Total module to update: {}, module list:{}".format(total_update, "".join(f"\n    + {item}" for item in cf.modules_to_update)))
    else:
        output("- No module to update")
    if not is_gui:
        print("=" * 70, "\n", sep='')
        input("Press Enter to continue...")
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
            if type(result) is dict and (
                    ('tag' in result and result['tag'] == 'reload') or ('url' in result and result['url'] == '/web')):
                # success, server response: client reload or redirect to home page
                end_time = time.time()
                if not color_allow:
                    output("- [{}/{}] Update module [{}] --- OK, run-time: {:.2f} seconds".format(count, total_update, tech_name, end_time - start_time))
                else:
                    output("- [{}/{}] Update module [{}] --- {}, run-time: {:.2f} seconds".format(count, total_update, tech_name, colored('OK', 'green'), end_time - start_time))
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
                output(
                    "- [{}/{}] Update module [{}] --- {}, module is not found!".format(count, total_update, tech_name, colored('FAILED', 'red')))

    if cf.language_to_update:
        # odoo from version 11.0 required patch to remote call internal function _update_translations
        required_patch_odoo_versions = (11.0, 12.0, 13.0, 14.0, 15.0)
        code = cf.language_to_update.strip().split(" ")[0] if " " in cf.language_to_update.strip() else cf.language_to_update.strip()
        output(f"- Updating translation for language code: {code}")
        log_text = ""
        try:
            code_ids = models.execute_kw(cf.db, uid, cf.password, "res.lang", "search", [[('code', '=', code)]])
            if code_ids:
                start_time = time.time()
                mods = models.execute_kw(cf.db, uid, cf.password, "ir.module.module", "search", [[('state', '=', 'installed')]])
                output(f"  - {len(mods)} modules to update translate")
                if remote_odoo_version in required_patch_odoo_versions:
                    result = models.execute_kw(cf.db, uid, cf.password, "ir.module.module", "remote_update_translation", [mods], {'filter_lang': code, 'context': {'overwrite': True}})
                else:
                    # using native function of odoo, response nothing
                    result = False
                    try:
                        models.execute_kw(cf.db, uid, cf.password, "ir.module.module", "update_translations", [mods], {'filter_lang': code, 'context': {'overwrite': True}})
                    except Exception as e:
                        if "cannot marshal None unless allow_none is enabled" in e.__str__():
                            result = True
                        else:
                            log_text = log_text + f"\nError report:\n{e.__str__()}" if log_text else e.__str__()

                if type(result) is dict and 'status' in result:
                    if result['status']:
                        output(f"  - Update success\n  - Duration: {int(time.time() - start_time)} second(s)")
                    else:
                        log_text += f"Update error logs:\n{result['error']}"
                        output(f"  - Update failed!\n  - Error message:\n{result['error']}")
                elif type(result) is bool:
                    if result:
                        output(f"  - Update success\n  - Duration: {int(time.time() - start_time)} second(s)")
                    else:
                        output(f"  - Update failed! Please check server logs")
                else:
                    output(f"  - Unknown response: {str(result)}")
            else:
                output(f"  - Could not find the language code: {code} active in database, please check it is correct and installed")
        except xmlrpc.client.Fault as e:
            log_text = log_text + f"\nXMLRPC error:\n{e.__str__()}" if log_text else e.__str__()
            log_file_path_lang = log_to_file(log_text, suffix="_trans_log_")
            output("    - Log file: {}".format(log_file_path_lang))


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
            sg.Text("Config file", size=(15, 1)),
            sg.Input(size=(25, 1), key='-CF-FILE-', enable_events=True),
            sg.FileBrowse(),
        ],
        [
            sg.Text("Modules to update", size=(15, 1)),
            sg.Multiline(size=(25, 4), key='-MODULES-')
        ],
        [
            sg.Text("Lang.(s) to update", size=(15, 1)),
            sg.OptionMenu(size=(20, 1),
                          values=("vi_VN (Vietnamese)", "en_US (English)", "fr_FR (French)",
                                  "es_ES (Spanish)", "zh_CN (Chinese (Simplified))"),
                          key='-LANGUAGE-')
            # sg.Multiline(size=(25, 4), key='-LANGUAGES-', default_text="vi_VN")
        ],
        [
            sg.Text('Admin password', size=(15, 1)),
            sg.Input(size=(25, 1), password_char='*', key='-ADMIN-PWD-')
        ],
        [
            sg.Text('Waiting time (sec)', size=(15, 1)),
            sg.OptionMenu(size=(20, 1),
                          values=(0, 30, 60, 120, 180, 300, 600, 900, 1800, 3600), default_value=0,
                          key='-WAITING-TIME-')
        ],
        [
            sg.Button("Run now", enable_events=True, key='-BTN-RUN-'),
            sg.Button("Cancel", enable_events=True, key='-BTN-CANCEL-')
        ]
    ]
    log_status = [
        [
            sg.Text("Status"),
            sg.Multiline(size=(50, 12), key='-STATUS-', disabled=True, autoscroll=True, auto_refresh=True)
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
    window.set_icon(resource_path('resources/icon.ico'))

    def update_status(text: str, clear: bool = False, sep="\n"):
        global gui_status_text, is_exit
        if is_exit:
            return
        if not clear:
            gui_status_text += f"{text}{sep}"
        else:
            gui_status_text = f"{text}{sep}"
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
                is_cancel = True
                break

    th_read_event = threading.Thread(target=read_event, daemon=True)
    th_read_event.start()

    current_cf_file = None

    while True:
        global event, values, is_cancel, is_running, is_exit
        # event, values = window.read()
        # if event == sg.WIN_CLOSED:
        #     break
        time.sleep(.001)
        if is_exit:
            break
        if values:
            if current_cf_file != values['-CF-FILE-']:
                current_cf_file = values['-CF-FILE-']
                update_status(f"---\nConfig file: {current_cf_file if current_cf_file else ''}")
                if current_cf_file and not values['-MODULES-']:
                    with open(current_cf_file, 'r') as f:
                        try:
                            config = json.load(f)
                            if 'modules_to_update' in config:
                                window['-MODULES-'].update("\n".join(config['modules_to_update']))
                        except Exception:
                            update_status(f"---\nError: Cannot read config file {current_cf_file}\nError logs:\n{traceback.format_exc()}")

        if event == '-BTN-RUN-':
            if not is_running:
                is_running = True
            else:
                return
            config_file = values['-CF-FILE-']
            modules = values['-MODULES-']
            language = values['-LANGUAGE-']
            admin_pwd = values['-ADMIN-PWD-']
            waiting_time = values['-WAITING-TIME-']
            waiting_time = int(waiting_time) if waiting_time else 0
            if config_file and (modules or language):
                start_update_msg = "=== Start update request... ==="
                no_admin_pw_msg = "*** Warning: The admin password is empty ***"
                if os.path.isfile(config_file):
                    allow_run = True
                    with open(config_file, 'r') as f:
                        try:
                            config = json.load(f)
                            erp_config = Config(**config)
                            erp_config.modules_to_update = []
                            if modules:
                                for item in modules.splitlines():
                                    if item.strip():
                                        erp_config.modules_to_update.append(item.strip())
                                if not erp_config.url or not erp_config.db:
                                    update_status("---\nError: Missing config for remote server URL and database name")
                                    allow_run = False
                                if not erp_config.modules_to_update and allow_run:
                                    update_status("---\nError: Please input module(s) to update")
                                    allow_run = False
                            if language:
                                erp_config.language_to_update = language
                                allow_run = True
                        except Exception:
                            allow_run = False
                            update_status(
                                f"---\nError: Reading config file failed!\nError logs:\n{traceback.format_exc()}")
                    if allow_run:
                        if admin_pwd:
                            erp_config.password = admin_pwd
                        else:
                            if not erp_config.password:
                                if waiting_time:
                                    update_status(no_admin_pw_msg)
                                else:
                                    start_update_msg += f"\n{no_admin_pw_msg}"
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
                            update_status(start_update_msg, clear=True)
                            try:
                                run_update(erp_config, update_status, True)
                                update_status("=== End ===")
                            except Exception:
                                update_status(
                                    f"---\nError: Request update error\nError logs:\n{traceback.format_exc()}")
                else:
                    update_status(f"=== ERROR ===\nThe config file \"{config_file}\" is not exit!", True)
            else:
                if not config_file:
                    update_status('Please select a config file...', clear=True)
                elif not modules:
                    update_status('Please input modules name (one per line) or language to update!', clear=True)
            is_running = False
        if event != sg.WIN_CLOSED:
            event = INIT_STATE_EVENT


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        console_mode()
    else:
        gui_mode()
