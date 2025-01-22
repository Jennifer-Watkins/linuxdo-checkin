import os
import random
import time
import functools
import sys

from loguru import logger
from playwright.sync_api import sync_playwright
from tabulate import tabulate


def retry_decorator(retries=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:  # 最后一次尝试
                        logger.error(f"函数 {func.__name__} 最终执行失败: {str(e)}")
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1}/{retries} 次尝试失败: {str(e)}")
                    time.sleep(1)
            return None

        return wrapper

    return decorator


def get_user_credentials():
    """获取所有用户凭证"""
    users = []
    i = 1
    while True:
        username = os.environ.get(f"USERNAME_{i}")
        password = os.environ.get(f"PASSWORD_{i}")
        if not username or not password:
            break
        users.append({"username": username, "password": password})
        i += 1
    return users


os.environ.pop("DISPLAY", None)
os.environ.pop("DYLD_LIBRARY_PATH", None)

HOME_URL = "https://linux.do/"


def mask_username(username, index):
    """将用户名转换为'第n位用户'的格式"""
    return f"第{index}位用户"


class LinuxDoBrowser:
    def __init__(self, username, password, user_index) -> None:
        self.username = username
        self.masked_name = mask_username(username, user_index)
        self.password = password
        self.pw = sync_playwright().start()
        self.browser = self.pw.firefox.launch(headless=True, timeout=30000)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(HOME_URL)

    def login(self):
        logger.info(f"开始登录: {self.masked_name}")
        self.page.click(".login-button .d-button-label")
        time.sleep(2)
        self.page.fill("#login-account-name", self.username)
        time.sleep(2)
        self.page.fill("#login-account-password", self.password)
        time.sleep(2)
        self.page.click("#login-button")
        time.sleep(10)
        user_ele = self.page.query_selector("#current-user")
        if not user_ele:
            logger.error(f"{self.masked_name} 登录失败")
            return False
        else:
            logger.info(f"{self.masked_name} 登录成功")
            return True

    def click_topic(self):
        topic_list = self.page.query_selector_all("#list-area .title")
        logger.info(f"{self.masked_name} 发现 {len(topic_list)} 个主题帖")
        for topic in topic_list:
            self.click_one_topic(topic.get_attribute("href"))

    @retry_decorator()
    def click_one_topic(self, topic_url):
        page = self.context.new_page()
        page.goto(HOME_URL + topic_url)
        if random.random() < 0.3:  # 0.3 * 30 = 9
            self.click_like(page)
        self.browse_post(page)
        page.close()

    def browse_post(self, page):
        prev_url = None
        # 开始自动滚动，最多滚动10次
        for _ in range(10):
            # 随机滚动一段距离
            scroll_distance = random.randint(550, 650)  # 随机滚动 550-650 像素
            logger.info(f"{self.masked_name} 向下滚动 {scroll_distance} 像素...")
            page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            logger.info(f"{self.masked_name} 已加载页面: {page.url}")

            if random.random() < 0.03:  # 33 * 4 = 132
                logger.success(f"{self.masked_name} 随机退出浏览")
                break

            # 检查是否到达页面底部
            at_bottom = page.evaluate("window.scrollY + window.innerHeight >= document.body.scrollHeight")
            current_url = page.url
            if current_url != prev_url:
                prev_url = current_url
            elif at_bottom and prev_url == current_url:
                logger.success(f"{self.masked_name} 已到达页面底部，退出浏览")
                break

            # 动态随机等待
            wait_time = random.uniform(2, 4)  # 随机等待 2-4 秒
            logger.info(f"{self.masked_name} 等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)

    def run(self):
        if not self.login():
            logger.error(f"{self.masked_name} 登录失败，跳过后续操作")
            return False
        self.click_topic()
        self.print_connect_info()
        return True

    def click_like(self, page):
        try:
            # 专门查找未点赞的按钮
            like_button = page.locator('.discourse-reactions-reaction-button[title="点赞此帖子"]').first
            if like_button:
                logger.info(f"{self.masked_name} 找到未点赞的帖子，准备点赞")
                like_button.click()
                logger.info(f"{self.masked_name} 点赞成功")
                time.sleep(random.uniform(1, 2))
            else:
                logger.info(f"{self.masked_name} 帖子可能已经点过赞了")
        except Exception as e:
            logger.error(f"{self.masked_name} 点赞失败: {str(e)}")

    def print_connect_info(self):
        logger.info(f"获取{self.masked_name}的连接信息")
        page = self.context.new_page()
        page.goto("https://connect.linux.do/")
        rows = page.query_selector_all("table tr")

        info = []

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                project = cells[0].text_content().strip()
                current = cells[1].text_content().strip()
                requirement = cells[2].text_content().strip()
                info.append([project, current, requirement])

        print(f"--------------Connect Info for {self.masked_name}-----------------")
        print(tabulate(info, headers=["项目", "当前", "要求"], tablefmt="pretty"))

        page.close()

    def cleanup(self):
        """清理浏览器资源"""
        try:
            self.context.close()
            self.browser.close()
            self.pw.stop()
        except Exception as e:
            logger.error(f"清理{self.masked_name}的浏览器资源时出错: {str(e)}")


if __name__ == "__main__":
    users = get_user_credentials()
    if not users:
        logger.error("未找到任何用户配置信息")
        sys.exit(1)

    logger.info(f"共发现 {len(users)} 个用户配置")
    success_count = 0
    
    for i, user in enumerate(users, 1):
        masked_name = mask_username(user['username'], i)
        logger.info(f"开始处理{masked_name}")
        browser = None
        try:
            browser = LinuxDoBrowser(user['username'], user['password'], i)
            if browser.run():
                success_count += 1
        except Exception as e:
            logger.error(f"处理{masked_name}时发生错误: {str(e)}")
        finally:
            if browser:
                browser.cleanup()
                logger.info(f"{masked_name}处理完成")
                # 在用户之间添加随机延迟，避免请求过于密集
                if i < len(users):
                    delay = random.uniform(5, 10)
                    logger.info(f"等待 {delay:.2f} 秒后处理下一个用户...")
                    time.sleep(delay)

    if success_count == 0:
        logger.error("所有用户处理均失败")
        sys.exit(1)
    else:
        logger.success(f"成功处理 {success_count}/{len(users)} 个用户")
