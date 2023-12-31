import os
import subprocess
import inspect
import platform
import requests
import zipfile
import threading
import trio

from multiprocessing.pool import ThreadPool, AsyncResult

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert

class WebElementAsyncResult:
    def __init__(self, ar:AsyncResult) -> None:
        self.__ar = ar
    
    def get(self) -> WebElement:
        return self.__ar.get()

class BoolAsyncResult:
    def __init__(self, ar:AsyncResult) -> None:
        self.__ar = ar
    
    def get(self) -> bool:
        return self.__ar.get()

class ChromeWebdriver():
    def __init__(self) -> None:
        self.separator = '_'
        self.driver_version_separator = 'd'
        self.browser_version_separator = 'b'
        self.default_downloaded_driver_name = "chromedriver"
        self.__websocket_listen_thread:threading.Thread = None
        self.__driver:webdriver.Chrome = None
        
    def initialize(self, 
                is_headless:bool,
                data_dir_name:str = "chrome_data",
                profile_name:str = "default",
                driver_name:str = "chromedriver",
                is_remove_profile_when_start:bool = False,
                is_remove_profile_when_close:bool = False,
                read_thread_count:int= 3,
                window_width:int= 800, 
                window_height:int= 600, 
                is_enable_image:bool= True, 
                user_agent:str= None,
                websocket_listening_function= None):
        
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
        self.__is_remove_profile_when_close = is_remove_profile_when_close

        self.__window_width = window_width
        self.__window_height = window_height
        self.__is_enable_image = is_enable_image
        self.__user_agent = user_agent
        
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
        if os.path.exists(profile_path):
            if is_remove_profile_when_start:
                self.__remove_directory(profile_path)
                os.mkdir(profile_path)
        else:
            os.mkdir(profile_path)
            
        self.__browser_thread = ThreadPool(1)
        self.__read_thread_pool = ThreadPool(read_thread_count)
        
        self.reset_driver(is_headless, window_width, window_height, is_enable_image, user_agent)
        
        if websocket_listening_function:
            self.reset_websocket_listener(websocket_listening_function)
        
    
    def reset_driver(self, 
                     is_headless:bool,
                     window_width:int= None, 
                     window_height:int= None, 
                     is_enable_image:bool= None, 
                     user_agent:str= None):
        
        if window_width == None:
            window_width = self.__window_width
        if window_height == None:
            window_height = self.__window_height
        if is_enable_image == None:
            is_enable_image = self.__is_enable_image
        if user_agent == None and not self.__user_agent:
            user_agent = self.__user_agent
        
        browser_version_by_bash = self.__get_browser_version_by_bash()
        driver_file_name = self.__find_driver_file(browser_version_by_bash)
        if driver_file_name == "":
            driver_file_name = self.__download_driver(browser_version_by_bash)
            
        driver_file_path = f"{self.__get_drivers_path()}/{driver_file_name}"
        temp_driver = self.__get_driver(is_headless, driver_file_path, window_width, window_height, is_enable_image, user_agent)
        browser_version = self.__get_browser_version_by_driver(temp_driver)
        driver_version = self.__get_driver_version(temp_driver)
        user_agent = self.__get_user_agent(temp_driver)
        temp_driver.quit()
        
        if driver_file_name == self.default_downloaded_driver_name:
            driver_file_name = self.__change_driver_filename(driver_file_name, browser_version, driver_version)
            driver_file_path = f"{self.__get_drivers_path()}/{driver_file_name}"
        
        self.__driver = self.__get_driver(is_headless, driver_file_path, window_width, window_height, is_enable_image, user_agent)
        self.__user_agent = self.__get_user_agent(self.__driver)
        
    def close(self):
        self.__read_thread_pool.close()
        self.__read_thread_pool.join()
        
        self.__browser_thread.close()
        self.__browser_thread.join()
        
        if self.__driver:
            self.__driver.quit()
            
        if self.__websocket_listen_thread:
            trio.run(self.send_cancel_listner)
            self.__websocket_listen_thread.join()
            
        if self.__is_remove_profile_when_close:
            profile_path = self.__get_profile_path()
            self.__remove_directory(profile_path)

    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Functions

    def open_async(self, url:str):
        '''
        Parameter
        -
        url (str): check 'http://'
        '''
        self.__browser_thread.apply_async(self.__driver.get, args=(url,))
    
    def open(self, timeout:float, url:str) -> bool:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        url (str): check 'http://' and exist end '/'\n
        Returns
        -
        (bool) : Return 'True' if equal url.
        '''
        self.__browser_thread.apply_async(self.__driver.get, args=(url,))
        result_url = self.url_to_be_async(timeout, url)
        return result_url.get()
    
    def url_to_be_async(self, timeout:float, url:str) -> BoolAsyncResult:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        url (str): url\n
        Returns
        -
        (BoolAsyncResult) : BoolAsyncResult.get() return bool
        '''
        expect_function = EC.url_to_be(url)
        return self.__read_thread_pool.apply_async(WebDriverWait(self.__driver, timeout).until, args=(expect_function,))
    
    def save_screenshot(self, filename:str) -> BoolAsyncResult:
        result = self.__read_thread_pool.apply_async(self.__driver.save_screenshot, args=(filename,))
        return result.get()
        
    def save_screenshot_async(self, filename:str) -> BoolAsyncResult:
        '''
        Parameters
        -
        filename (str): image filename\n
        Returns
        -
        BoolAsyncResult : BoolAsyncResult.get() return bool
        -
        '''
        return self.__read_thread_pool.apply_async(self.__driver.save_screenshot, args=(filename,))
    
    def get_element_xpath_async(self, timeout:float, xpath:str) -> WebElementAsyncResult:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        xpath (str): xpath string\n
        return
        -
        WebElement\n
        '''
        expect_function = EC.presence_of_element_located((By.XPATH, xpath))
        async_result = self.__read_thread_pool.apply_async(WebDriverWait(self.__driver, timeout).until, args=(expect_function,))
        return WebElementAsyncResult(async_result)
    
    def get_element_xpath(self, timeout:float, xpath:str) -> WebElement:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        xpath (str): xpath string\n
        return
        -
        WebElement\n
        '''
        expect_function = EC.presence_of_element_located((By.XPATH, xpath))
        result = self.__read_thread_pool.apply_async(WebDriverWait(self.__driver, timeout).until, args=(expect_function,))
        return result.get()
    
    def get_element_id(self, timeout:float, id:str) -> WebElement:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        xpath (str): xpath string\n
        return
        -
        WebElement\n
        '''
        expect_function = EC.presence_of_element_located((By.ID, id))
        result = self.__read_thread_pool.apply_async(WebDriverWait(self.__driver, timeout).until, args=(expect_function,))
        return result.get()
    
    def get_elements_by_tag_name(self, timeout:float, tag_name:str) -> WebElement:
        '''
        Parameters
        -
        timeout (float): timeout seconds\n
        xpath (str): xpath string\n
        return
        -
        WebElement\n
        '''
        expect_function = EC.presence_of_all_elements_located((By.TAG_NAME, tag_name))
        result = self.__read_thread_pool.apply_async(WebDriverWait(self.__driver, timeout).until, args=(expect_function,))
        return result.get()
    
    
    # def input_text(self, input_element:WebElement, text:str):
    #     input_element.click()
    #     for c in text:
    #         input_element.send_keys(Keys.DOWN, c)
    
    # def input_text_async(self, input_element:WebElement, text:str):
    #     self.__main_thread_pool.apply_async(self.input_text, args=(input_element, text))
    
    # def click_async(self, element:WebElement):
    #     self.__main_thread_pool.apply_async(element.click)
    
    # def get_alert(self, timeout:float) -> Alert | bool:
    #     '''
    #     Main Thread Pool\n
    #     return Alert or False
    #     -
    #     '''
    #     expect_function = EC.alert_is_present()
    #     result = self.__main_thread_pool.apply_async(WebDriverWait(self.driver, timeout).until, args=(expect_function,))
    #     return result.get()
        
    # def url_to_be_async(self, timeout:float, url:str) -> AsyncResult:
    #     '''
    #     Main Thread Pool\n
    #     return AsyncResult
    #     -
    #     AsyncResult.get() return bool
    #     -
    #     '''
    #     expect_function = EC.url_to_be(url)
    #     return self.__main_thread_pool.apply_async(WebDriverWait(self.driver, timeout).until, args=(expect_function,))
    
    # def get_url_to_be_first(self, timeout:float, url_list:list[str]):
    #     '''
    #     Not Main Thread Pool (ThreadPoolExecutor)
    #     '''
    #     def temp_func(_timeout:float, _url:str, _q:queue.Queue):
    #         result = WebDriverWait(self.driver, _timeout).until(EC.url_to_be(_url))
    #         if result:
    #             _q.put_nowait(_url)
        
    #     url_count = len(url_list)
    #     temp_q = queue.Queue()
    #     future_list = []
        
    #     executor = concurrent.futures.ThreadPoolExecutor(url_count)
    #     for url in url_list:
    #         future = executor.submit(temp_func, timeout, url, temp_q)
    #         future_list.append(future)
            
    #     url_result = temp_q.get()
        
    #     for _f in future_list:
    #         f:concurrent.futures._base.Future = _f
    #         if f.done() == False:
    #             f.cancel()
                
    #     return url_result

    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Privates
    # Path and File
    def __get_data_path(self): return f"{self.__running_path}/{self.__data_dir_name}"
    def __get_drivers_path(self): return f"{self.__running_path}/{self.__data_dir_name}/drivers"
    def __get_profiles_path(self): return f"{self.__running_path}/{self.__data_dir_name}/profiles"
    def __get_profile_path(self): return f"{self.__running_path}/{self.__data_dir_name}/profiles/{self.__profile_name}"
    
    def __remove_directory(self, path:str):
        if os.path.isdir(path):
            path_list = os.listdir(path)
            for p in path_list:
                joined_path = os.path.join(path, p)
                self.__remove_directory(joined_path)
            os.rmdir(path)
        elif os.path.isfile(path):
            os.remove(path)
    
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
            
        for file_name, _, file_chrome_version in driver_file_version_list:
            if file_name == self.__driver_name:
                return file_name
            
        for file_name, _, file_chrome_version in driver_file_version_list:
            if file_name == self.default_downloaded_driver_name:
                return file_name
            
        return ""
    
    def __change_driver_filename(self, driver_file_name:str, browser_version:str, driver_version:str) -> str:
        dst_filename = f"{self.__driver_name}{self.separator}{self.browser_version_separator}{browser_version}{self.separator}{self.driver_version_separator}{driver_version}"
        src_path = f"{self.__get_drivers_path()}/{driver_file_name}"
        dst_path = f"{self.__get_drivers_path()}/{dst_filename}"
        os.rename(src_path, dst_path)
        return dst_filename

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
                splitted_file_name[1][0] == self.browser_version_separator:
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
    
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Version
    def __get_driver_version(self, driver:webdriver.Chrome) -> str: return driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0]
    def __get_browser_version_by_driver(self, driver:webdriver.Chrome) -> str: return driver.capabilities['browserVersion'].split(' ')[0]
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
    
    
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Download Driver
    def __get_current_platfrom_for_driver_url(self) -> str:
        uname = platform.uname()
        platform_name = ""
        if uname.system == "Darwin":
            platform_name = f"mac-{uname.machine}"
            
        if uname.system == "Linux":
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
    
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Driver
    
    def __get_user_agent(self, driver:webdriver.Chrome) -> str:
        user_agent:str = driver.execute_script("return navigator.userAgent")
        user_agent = user_agent.replace('HeadlessChrome/', 'Chrome/')
        return user_agent
        
    def __get_driver(self,
                     is_headless:bool,
                     driver_file_path:str, 
                     window_width:int, 
                     window_height:int, 
                     is_enable_image:bool, 
                     user_agent:str == None) -> webdriver.Chrome:
        options = webdriver.ChromeOptions()
        if is_headless:
            options.add_argument('headless')
            options.add_argument('disable-gpu')
            options.add_argument('disable-extensions')
            options.add_argument('no-sandbox')
            options.add_argument('disable-setuid-sandbox')
            options.add_argument('disable-dev-shm-usage')
            options.add_argument('disable-user-media-security=true')
            options.add_argument('ignore-certificate-errors')
            options.add_argument(f'window-size={window_width},{window_height}')
            options.add_argument(f'user-data-dir={self.__get_profile_path()}')
        
        if user_agent:
            options.add_argument(f'user_agent={user_agent}')
        
        if is_enable_image is False:
            options.add_argument('blink-settings=imagesEnabled=false')
            options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

        options.add_argument('lang=ko_KR')
        
        service = Service(executable_path=driver_file_path)
        return webdriver.Chrome(service=service, options=options)
        
    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    # Websocket Listener
    '''CDP devtools regist'''
    async def send_cancel_listner(self):
        async with await trio.open_tcp_stream("127.0.0.1", 12346) as s:
            await s.send_all(b'quit')
        
    async def wait_cancel_listener(self, cancel_scope):      
        async def receiver(server_stream):    
            await server_stream.receive_some(1024)    
            cancel_scope.cancel()    
        await trio.serve_tcp(receiver, 12346)
        
    async def set_websocket_listener(self, websocket_listening_function):
        async with self.__driver.bidi_connection() as connection:
            await connection.session.execute(connection.devtools.network.enable())
            listener = connection.session.listen(connection.devtools.network.WebSocketFrameReceived) # selenium.webdriver.common.devtools.v114.network.WebSocketFrameReceived
            async with trio.open_nursery() as nursery:
                nursery.start_soon(websocket_listening_function, listener)
                nursery.start_soon(self.wait_cancel_listener, nursery.cancel_scope)
    
    def reset_websocket_listener(self, websocket_listening_function):
        self.__websocket_listen_thread = threading.Thread(target=trio.run, args=(self.set_websocket_listener, *(websocket_listening_function,)))
        self.__websocket_listen_thread.start()