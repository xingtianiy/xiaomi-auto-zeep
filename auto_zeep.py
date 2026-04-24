#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米运动/Zepp Life 原生官方API 刷步
去除第三方中转、直连华米官方服务器
"""
import requests
import random
import time
import json
import logging
from datetime import datetime
import os
import hashlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 账号读取(保留原逻辑) ====================
def get_accounts_from_env():
    accounts = []
    for i in range(1, 6):
        username = os.getenv(f'ACCOUNT{i}_USERNAME')
        password = os.getenv(f'ACCOUNT{i}_PASSWORD')
        if username and password:
            accounts.append({"username": username, "password": password})
            logger.info(f"✅ 成功加载账号 {i}: {username}")
    if not accounts:
        logger.warning("⚠️ 未找到任何账号配置")
    return accounts

ACCOUNTS = get_accounts_from_env()

# ==================== 步数时段规则(完全保留你原有) ====================
STEP_RANGES = {
    8: {"min": 6000, "max": 10000},
    12: {"min": 8000, "max": 14000},
    16: {"min": 10000, "max": 18000},
    20: {"min": 12000, "max": 22000},
    22: {"min": 15000, "max": 24000}
}
DEFAULT_STEPS = 24465

# ==================== 原生官方API核心类 ====================
class MiFitOfficial:
    # 华米官方基础域名
    BASE_URL = "https://api-mifit.huami.com/v1"

    def __init__(self):
        self.session = requests.Session()
        # 官方标准请求头
        self.headers = {
            "User-Agent": "ZeppLife/6.11.0 (Android; Mobile)",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.access_token = ""
        self.user_id = ""
        self.device_id = self.gen_device_id()

    @staticmethod
    def gen_device_id():
        """随机生成设备ID，模拟真实手机"""
        return "".join(random.choice("0123456789abcdef") for _ in range(16))

    @staticmethod
    def md5(pwd):
        """官方密码MD5加密规则"""
        return hashlib.md5(pwd.encode("utf-8")).hexdigest()

    def login(self, account, pwd):
        """
        原生官方登录接口
        接口: POST /v1/auth/login
        """
        try:
            url = f"{self.BASE_URL}/auth/login"
            payload = {
                "account": account,
                "password": self.md5(pwd),
                "deviceId": self.device_id,
                "deviceType": 1
            }
            res = self.session.post(url, json=payload, headers=self.headers, timeout=30)
            data = res.json()

            if data.get("code") == 200:
                self.access_token = data["data"]["accessToken"]
                self.user_id = data["data"]["userId"]
                logger.info("✅ 官方账号登录成功")
                return True
            else:
                logger.error(f"❌ 登录失败: {data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ 登录请求异常: {str(e)}")
            return False

    def upload_step(self, steps):
        """
        原生步数上报接口
        接口: POST /v1/step/upload
        """
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            # 换算简易卡路里、距离(官方必填字段)
            distance = round(steps * 0.7 / 1000, 2)
            calorie = round(steps * 0.04, 2)

            step_data = [{
                "date": today,
                "steps": steps,
                "distance": distance,
                "calories": calorie
            }]

            url = f"{self.BASE_URL}/step/upload"
            payload = {
                "userid": self.user_id,
                "access_token": self.access_token,
                "deviceid": self.device_id,
                "device_type": 1,
                "data_json": json.dumps(step_data)
            }

            res = self.session.post(url, json=payload, headers=self.headers, timeout=30)
            data = res.json()

            if data.get("code") == 200:
                logger.info(f"✅ 原生API步数上报成功｜步数:{steps}")
                return True
            else:
                logger.error(f"❌ 步数上报失败: {data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ 上报请求异常: {str(e)}")
            return False

# ==================== 保留你的智能步数生成逻辑 ====================
def get_current_steps(account_index=0):
    current_hour = datetime.now().hour
    logger.info(f"🕐 当前小时: {current_hour}")
    closest_hour = None
    min_diff = float('inf')

    for hour in STEP_RANGES.keys():
        diff = abs(current_hour - hour)
        if diff < min_diff:
            min_diff = diff
            closest_hour = hour

    if min_diff <= 2 and closest_hour in STEP_RANGES:
        cfg = STEP_RANGES[closest_hour]
        base = random.randint(cfg["min"], cfg["max"])
        offset = random.randint(-500, 500)
        steps = max(1000, base + offset)
    else:
        base = DEFAULT_STEPS
        offset = random.randint(-1000, 1000)
        steps = max(1000, base + offset)
    return steps

# ==================== 主运行逻辑 ====================
def main():
    logger.info("🎯 【Zepp Life 原生官方API 刷步任务启动】")
    if not ACCOUNTS:
        logger.error("❌ 无账号配置，退出")
        exit(1)

    success_count = 0
    fail_count = 0

    for idx, acc in enumerate(ACCOUNTS):
        username = acc["username"]
        pwd = acc["password"]
        logger.info(f"\n---------- 开始处理账号: {username} ----------")

        # 初始化官方API实例
        client = MiFitOfficial()
        # 1.登录
        if not client.login(username, pwd):
            fail_count += 1
            continue
        # 2.生成步数
        steps = get_current_steps(idx)
        logger.info(f"🔢 本次上报步数: {steps}")
        # 3.上报步数
        if client.upload_step(steps):
            success_count += 1
        else:
            fail_count += 1

        # 账号间隔
        if idx + 1 < len(ACCOUNTS):
            time.sleep(5)

    logger.info(f"\n========== 任务结束 ==========")
    logger.info(f"✅ 成功:{success_count}  ❌ 失败:{fail_count}")
    if fail_count == 0:
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    main()
