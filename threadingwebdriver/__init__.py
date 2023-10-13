import os
import subprocess
import inspect
import platform
import requests
import zipfile

from multiprocessing.pool import ThreadPool, AsyncResult

from selenium import webdriver

class ChromeWebdriver():
    separator = '_'
    driver_version_separator = 'd'
    chrome_version_separator = 'c'
    
    default_downloaded_driver_name = "chromedriver"
    
    def __init__(self) -> None:
        pass
    
    def initialize(self, 
                data_dir_name:str = "chrome_data",
                profile_name:str = "default",
                driver_name:str = "chromedriver",
                is_remove_profile_when_start:bool = False,
                is_remove_profile_when_close:bool = False,
                read_thread_count:int = 3,
                window_width:int=800, 
                window_height:int=600, 
                is_enable_image:bool=False, 
                websocket_listening_function=None,
                user_agent:str=None):
        
        uname = platform.uname()
        if uname.system == "Windows":
            raise RuntimeError("Not implement windows")
        
        frames = inspect.stack()
        caller_frame = frames[1]
        
        caller_filename = caller_frame.filename
        self.__running_path = '/'.join(caller_filename.split('/')[:-1])
        
        self.__data_dir_name = data_dir_name
        self.__profile_name = profile_name
        self.__driver_name = driver_name
                
        self.__check_paths()
        
        self.__browser_thread = ThreadPool(1)
        self.__read_page_thread_pool = ThreadPool(read_thread_count)
        
        self.reset_driver()
    
    def reset_driver(self):
        browser_version_by_bash = self.__get_browser_version_by_bash()
        driver_file_name = self.__find_driver_file(browser_version_by_bash)
        if driver_file_name == "":
            download_file_name = self.__download_driver(browser_version_by_bash)
            print(download_file_name)
        
        
    def __get_browser_version_by_bash(self) -> str:
        result_bytes = b''
        uname = platform.uname()
        if uname.system == "Darwin":
            result_bytes = subprocess.check_output(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'])
            
        elif uname.system == "Linux":
            result_bytes = subprocess.check_output(['google-chrome', '--version'])
        
        else:    
            raise RuntimeError("Unknown OS type")
        
        result_str = result_bytes.decode()
        return result_str.split(' ')[2]
    
    def __find_driver_file(self, chrome_version:str) -> str:
        driver_files = self.__get_driver_files()
        driver_file_version_list = []
        for file_name in driver_files:
            file_driver_version, file_chrome_version = self.__get_driver_versions_from_file_name(file_name)
            if file_driver_version == chrome_version:
                return file_name
            driver_file_version_list.append((file_name, file_driver_version, file_chrome_version))
        
        for file_name, _, file_chrome_version in driver_file_version_list:
            if file_chrome_version == chrome_version:
                return file_name
            
        return ""
            
    def __download_driver(self, chrome_version:str, platform_name:str = 'linux64'):
        platform_name = self.__get_current_platfrom_for_driver_url()
        download_url = self.__get_driver_url(chrome_version, platform_name)
        result_download = True
        drivers_dir_full_path = self.__get_drivers_path()
        download_path = f"{drivers_dir_full_path}/{self.__driver_name}.zip"
        
        with open(download_path, "wb") as file:
            response = requests.get(download_url)
            if response.status_code == 404:
                result_download = False
                print(f"Download Chrome Driver Failed. status_code:{response.status_code} url:{download_url} ")
            elif response.status_code == 200:
                file.write(response.content)
            else:
                print(f"Download Chrome Driver Failed. status_code:{response.status_code} url:{download_url} ")
                
        result_filename = ""
        if result_download:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(drivers_dir_full_path)
            src_path = f"{drivers_dir_full_path}/chromedriver-{platform_name}/{self.default_downloaded_driver_name}"
            dst_path = f"{drivers_dir_full_path}/{self.__driver_name}"
            os.rename(src_path, dst_path) # overwrite if exist dst 
            os.chmod(dst_path, 755)
            os.remove(download_path)
            self.__remove_directory(f"{drivers_dir_full_path}/chromedriver-{platform_name}")
            result_filename = self.__driver_name
        return result_filename
    
    def __remove_directory(self, path:str):
        if os.path.isdir(path):
            path_list = os.listdir(path)
            for p in path_list:
                joined_path = os.path.join(path, p)
                self.__remove_directory(joined_path)
            os.rmdir(path)
        elif os.path.isfile(path):
            os.remove(path)
    
    def __get_current_platfrom_for_driver_url(self) -> str:
        uname = platform.uname()
        platform_name = ""
        if uname.system == "Darwin":
            platform_name = f"mac-{uname.machine}"
            
        if uname.system == "linux":
            platform_name = "linux64"
        return platform_name
    
    def __get_driver_url(self, chrome_version:str, platform_name:str) -> str:
        '''
        Parameter
        -
        chrome_version (str): chrome browser app version.\n
        platform_name (str):
        'linux64'
        'mac-arm64'
        'mac-x64'
        'win32'
        'win64'
        '''
        url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        response = requests.get(url)
        response_json = response.json()
        versions = response_json['versions']
        
        download_url = ""
        for v in versions:
            if v['version'] == chrome_version:
                for platforms in v['downloads']['chromedriver']:
                    if platforms['platform'] == platform_name:
                        download_url = platforms['url']
        
        if download_url == "":
            url = "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json"
            response = requests.get(url)
            response_json = response.json()
            
            splitted_chrome_version = chrome_version.split('.')
            build_chrome_version = '.'.join(splitted_chrome_version[:3])
            
            build = response_json["builds"][build_chrome_version]
            for platforms in build['downloads']['chromedriver']:
                if platforms['platform'] == platform_name:
                    download_url = platforms['url']
                        
        return download_url

        
    
    def __get_driver_versions_from_file_name(self, file_name:str) -> (str, str):
        '''
        Parameter
        -
        file_name (str): source driver file name\n
        return
        -
        (str, str): real version, release version
        '''
        real_driver_version = ""
        release_driver_version = ""
        splitted_file_name = file_name.split(self.separator)
        if 0<len(splitted_file_name) and splitted_file_name[0] == self.__driver_name:
            if 1<len(splitted_file_name) and\
                0<len(splitted_file_name[1]) and\
                splitted_file_name[1][0] == self.chrome_version_separator:
                real_driver_version = splitted_file_name[1][1:]
            
            if 2<len(splitted_file_name) and\
                0<len(splitted_file_name[2]) and\
                splitted_file_name[2][0] == self.driver_version_separator:
                release_driver_version = splitted_file_name[2][1:]
                
        return real_driver_version, release_driver_version
        
        
    def __get_driver_files(self) -> list[str]:
        drivers_path = self.__get_drivers_path()
        driver_files = []
        file_names = os.listdir(drivers_path)
        for file_name in file_names:
            file_path = os.path.join(drivers_path, file_name)
            if os.path.isfile(file_path):
                if file_name == self.__driver_name:
                    driver_files.append(file_name)
                else:
                    splitted_file_name = file_name.split(self.separator)
                    if splitted_file_name[0] == self.__driver_name:
                        driver_files.append(file_name)
        driver_files.sort()
        return driver_files
    
    def __get_data_path(self):
        return f"{self.__running_path}/{self.__data_dir_name}"
    
    def __get_drivers_path(self):
        return f"{self.__running_path}/{self.__data_dir_name}/drivers"
    
    def __get_profiles_path(self):
        return f"{self.__running_path}/{self.__data_dir_name}/profiles"
    
    def __get_profile_path(self):
        return f"{self.__running_path}/{self.__data_dir_name}/profiles/{self.__profile_name}"
    
    def __check_paths(self):
        print("__running_path:", self.__running_path)
        
        data_path = self.__get_data_path()
        if not os.path.exists(data_path):
            os.mkdir(data_path)
            
        drivers_path = self.__get_drivers_path()
        if not os.path.exists(drivers_path):
            os.mkdir(drivers_path)
        
        profiles_path = self.__get_profiles_path()
        if not os.path.exists(profiles_path):
            os.mkdir(profiles_path)
            
        profile_path = self.__get_profile_path()
        if not os.path.exists(profile_path):
            os.mkdir(profile_path)
        
        