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
    config_file: str = ""

    def __init__(self, url: str, db: str, password: str, modules_to_update: list, username: str = "admin"):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.modules_to_update = modules_to_update
        self.language_to_update = ""


def log_to_file(log_text: str, suffix="_execute_log_", config_file: str = ""):
    log_dir = os.path.join(base_dir, 'logs')
    config_name = os.path.basename(config_file) if config_file else os.path.basename(sys.argv[1])
    if not os.path.isdir(log_dir):
        os.mkdir(log_dir)
    log_file = os.path.join(log_dir, config_name.replace('.json', '') + suffix + str(int(time.time())) + '.txt')
    with open(log_file, 'w+', errors='ignore') as f_log:
        f_log.write(log_text.replace('\\\\n', "\n").replace('\\n', "\n"))
    return log_file


def run_update(cf: Config, output_handler: callable = None, is_gui: bool = False):
    global color_allow
    if is_gui:
        color_allow = False

    def output(msg: str, sep="\n", font: str = None, text_color: str = None):
        if not callable(output_handler):
            print(msg, sep=sep)
        else:
            output_handler(msg, sep=sep, font=font, text_color=text_color)

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
        if "." in _version:
            _version = _version.split(".")[0]
        if str.isnumeric(_version):
            _version = int(_version)
        try:
            _uid = common.authenticate(cf.db, cf.username, cf.password, {})
            output("connected!", text_color="green")
            output("- Remote server version: ", sep="")
            output(_version, font="arial 9 bold")
        except ConnectionRefusedError as e:
            output("error!\n" + str(e))
            return
        _models = xmlrpc.client.ServerProxy(f'{cf.url}/xmlrpc/2/object', allow_none=allow_none)
        return _models, _uid, _version

    output("- ERP server: ", sep="")
    output(cf.url, font="Consolas 9", text_color="green")
    output("- Database: ", sep="")
    output(cf.db, font="Consolas 9", text_color="green")

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
        output("- Total module to update: ", sep="")
        output(str(total_update), font="arial 9 bold", sep="")
        _m_list = "".join(f"\n    + {item}" for item in cf.modules_to_update)
        output(f", module list:{_m_list}")
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
            output(f"- Requesting update module: ", sep="")
            output(tech_name, font="arial 9 bold", sep="")
            output("...")
            ids = models.execute_kw(cf.db, uid, cf.password, model_name, "search", [[('name', '=', tech_name.strip())]])
        except xmlrpc.client.Fault as e:
            if 'Access denied' in str(e):
                output("- ", sep="")
                output("'Access denied'", font="arial 9 bold", sep="")
                output(" please check user account and login password!")
            else:
                output("- ", sep="")
                output("Error: ", font="arial 9 bold", sep="")
                output(str(e), font="Consolas 9")
            return
        if ids:
            start_time = time.time()
            log_file_path = None
            server_busy = False
            try:
                result = models.execute_kw(cf.db, uid, cf.password, model_name, update_method, [ids])
            except xmlrpc.client.Fault as e:
                fault = e.__str__()
                log_file_path = log_to_file(fault, config_file=cf.config_file)
                result = None
                if 'The server is busy right now' in fault:
                    server_busy = True

            if (type(result) is dict and (('tag' in result and result['tag'] == 'reload') or ('url' in result and result['url'] == '/web'))) or server_busy:
                # success, server response: client reload or redirect to home page
                end_time = time.time()
                output(f"- [{count}/{total_update}] Update module ", sep="")
                output(tech_name, font='arial 9 bold', sep="")
                output(" --- ", sep="")
                output("OK" if not server_busy else "OK (server busy!)", font='arial 9', text_color='green', sep="")
                output(f", run-time: {end_time - start_time:.2f} seconds" if not server_busy else ', run-time: n/a')
            else:
                output(f"- [{count}/{total_update}] Update module ", sep="")
                output(tech_name, font='arial 9 bold', sep="")
                output(" --- ", sep="")
                output("FAILED", font='arial 9', text_color='red', sep="")
                output(", RESPONSE: ", sep="")
                output(result, font="Consolas 9")
            if log_file_path:
                output("    - Log file: ", sep="")
                output(log_file_path, font="Consolas 9")
        else:
            output(f"- [{count}/{total_update}] Update module ", sep="")
            output(tech_name, font='arial 9 bold', sep="")
            output(" --- ", sep="")
            output("module is not found!", font='arial 9', text_color='red')

    if cf.language_to_update:
        # odoo from version 11.0 required patch to remote call internal function _update_translations
        try:
            required_patch_odoo_versions = remote_odoo_version >= 11
        except TypeError:
            required_patch_odoo_versions = False
            output("- Cannot get remote server version from text: ", sep="")
            output(remote_odoo_version, font="arial 9 bold")
        code = cf.language_to_update.strip().split(" ")[0] if " " in cf.language_to_update.strip() else cf.language_to_update.strip()
        output("- Updating translation for language code: ", sep="")
        output(code, font="arial 9 bold")
        log_text = ""
        try:
            code_ids = models.execute_kw(cf.db, uid, cf.password, "res.lang", "search", [[('code', '=', code)]])
            if code_ids:
                start_time = time.time()
                mods = models.execute_kw(cf.db, uid, cf.password, "ir.module.module", "search", [[('state', '=', 'installed')]])
                output("  - ", sep="")
                output(str(len(mods)), font="arial 9 bold", sep="")
                output(" modules to update translate")
                if required_patch_odoo_versions:
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
                        output("  - Update ", sep="")
                        output("success", text_color="green")
                        output("  - Duration: ", sep="")
                        output(f"{int(time.time() - start_time)}", font="arial 9 bold", sep="")
                        output(" second(s)")
                    else:
                        log_text += f"Update error logs:\n{result['error']}"
                        output("  - Update ", sep="")
                        output("failed", text_color="red")
                        output("  - Error message: ", sep="")
                        output(result['error'], font="Consolas 9")
                elif type(result) is bool:
                    if result:
                        output("  - Update ", sep="")
                        output("success", text_color="green")
                        output("  - Duration: ", sep="")
                        output(f"{int(time.time() - start_time)}", font="arial 9 bold", sep="")
                        output(" second(s)")
                    else:
                        output("  - Update ", sep="")
                        output("failed", text_color="red", sep="")
                        output(". Please check server logs.")
                else:
                    output("  - Unknown response: ", sep="")
                    output(str(result), font="Consolas 9")
            else:
                output(f"  - Could not find the language code: ", sep="")
                output(code, font="arial 9 bold", sep="")
                output(" active in database, please check it is correct and installed")
        except xmlrpc.client.Fault as e:
            log_text = log_text + f"\nXMLRPC error:\n{e.__str__()}" if log_text else e.__str__()
            log_file_path_lang = log_to_file(log_text, suffix="_trans_log_", config_file=cf.config_file)
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
                          values=("", "vi_VN (Vietnamese)", "en_US (English)", "fr_FR (French)",
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

    def update_status(text: str, clear: bool = False, sep="\n", font: str = None, text_color: str = None):
        global is_exit
        if is_exit:
            return
        if not clear:
            window['-STATUS-'].print(text, end=sep, font=font, text_color=text_color)
        else:
            window['-STATUS-'].update("")
            window['-STATUS-'].print(text, end=sep, font=font, text_color=text_color)

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
                update_status("---")
                update_status("Config file: ", sep="", font="arial 9 bold")
                update_status(current_cf_file if current_cf_file else '')
                if current_cf_file:
                    with open(current_cf_file, 'r') as f:
                        try:
                            config = json.load(f)
                            if 'modules_to_update' in config and not values['-MODULES-']:
                                window['-MODULES-'].update("\n".join(config['modules_to_update']))
                            update_status("  - ERP server: ", font="Consolas 9", sep="")
                            update_status(config['url'], font="Consolas 9 bold")
                            update_status("  - Database: ", font="Consolas 9", sep="")
                            update_status(config['db'], font="Consolas 9 bold")
                            update_status("  - Username: ", font="Consolas 9", sep="")
                            update_status(config['username'], font="Consolas 9 bold")
                            update_status("  - Password: ", font="Consolas 9", sep="")
                            if config['password']:
                                update_status("YES", font="Consolas 9 bold", text_color="green")
                            else:
                                update_status("NO", font="Consolas 9 bold", text_color="red")
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
                if os.path.isfile(config_file):
                    allow_run = True
                    with open(config_file, 'r') as f:
                        try:
                            config = json.load(f)
                            erp_config = Config(**config)
                            erp_config.modules_to_update = []
                            erp_config.config_file = current_cf_file
                            if modules:
                                for item in modules.splitlines():
                                    if item.strip():
                                        erp_config.modules_to_update.append(item.strip())
                                if not erp_config.url or not erp_config.db:
                                    update_status("---\nError: ", font="arial 9 bold", sep="")
                                    update_status("Missing config for remote server URL and/or database name")
                                    allow_run = False
                                if not erp_config.modules_to_update and allow_run:
                                    update_status("---\nError: ", font="arial 9 bold", sep="")
                                    update_status("Please input module(s) to update")
                                    allow_run = False
                            if language:
                                erp_config.language_to_update = language
                                allow_run = True
                        except Exception:
                            allow_run = False
                            update_status("---\nError: ", font="arial 9 bold", sep="")
                            update_status(f"Reading config file failed!")
                            update_status(f"Error logs:", font="arial 9 bold")
                            update_status(f"{traceback.format_exc()}", font="Consolas 9")
                    if allow_run:
                        if admin_pwd:
                            erp_config.password = admin_pwd
                            update_status("- Auth using password is set from input")
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
                            update_status('=== CANCEL ===', font="arial 9 bold")
                            is_cancel = False
                        else:
                            update_status("=== UPDATE START ===", clear=True, font="arial 9 bold")
                            try:
                                run_update(erp_config, update_status, True)
                                update_status("=== UPDATE END ===", font="arial 9 bold")
                            except Exception:
                                log_text = traceback.format_exc()
                                log_file = log_to_file(log_text, config_file=current_cf_file)
                                update_status(f"\n---")
                                update_status("Error: ", font="arial 9 bold", sep="")
                                update_status("The update request error, shorten logs:")
                                update_status(f"{log_text[:100]}\n...\n...{log_text[-100:]}", font="Consolas 9")
                                update_status("Log file: ", font="arial 9 bold", sep="")
                                update_status(log_file)
                                update_status("=== UPDATE END ===", font="arial 9 bold")
                else:
                    update_status(f"=== ERROR ===", clear=True, font="arial 9 bold")
                    update_status(f"The config file ", sep="")
                    update_status(config_file, font="arial 9 bold")
                    update_status(" is not exist!")
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
