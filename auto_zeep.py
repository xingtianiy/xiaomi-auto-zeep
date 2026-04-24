#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zepp Life 小米运动 最新原生API
修复旧登录接口失效、签名缺失、登录失败:None 问题
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

# ==================== 读取账号（完全不变） ====================
def get_accounts_from_env():
    accounts = []
    for i in range(1, 6):
        username = os.getenv(f'ACCOUNT{i}_USERNAME')
        password = os.getenv(f'ACCOUNT{i}_PASSWORD')
        if username and password:
            accounts.append({"username": username, "password": password})
            logger.info(f"✅ 成功加载账号 {i}: {username}")
    if not accounts:
        logger.warning("⚠️ 未找到任何账号环境变量配置")
    return accounts

ACCOUNTS = get_accounts_from_env()

# ==================== 步数规则（保留你原版） ====================
STEP_RANGES = {
    8: {"min": 6000, "max": 10000},
    12: {"min": 8000, "max": 14000},
    16: {"min": 10000, "max": 18000},
    20: {"min": 12000, "max": 22000},
    22: {"min": 15000, "max": 24000}
}
DEFAULT_STEPS = 24465

# ==================== 修复版 官方API 核心类 ====================
class ZeppLifeApi:
    BASE_URL = "https://api-mifit.huami.com"
    APP_KEY = "huami20150403"
    APP_SECRET = "a2b7d0967d4e8f1c3a5b902f76e4d123"

    def __init__(self):
        self.session = requests.Session()
        self.device_id = self.random_device_id()
        self.access_token = ""
        self.user_id = ""
        self.headers = {
            "User-Agent": "ZeppLife/7.10.0 (Linux; Android 13)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip"
        }

    @staticmethod
    def random_device_id():
        return "".join(random.sample("0123456789abcdef", 16))

    @staticmethod
    def md5(s):
        return hashlib.md5(s.encode()).hexdigest()

    def get_sign(self, params: dict):
        """生成官方必填签名"""
        items = sorted(params.items())
        raw = "".join([f"{k}{v}" for k, v in items]) + self.APP_SECRET
        return self.md5(raw)

    def login(self, account, pwd):
        """新版合规登录接口"""
        try:
            url = f"{self.BASE_URL}/v2/auth/login"
            params = {
                "account": account,
                "password": self.md5(pwd),
                "deviceId": self.device_id,
                "deviceType": 1,
                "appKey": self.APP_KEY,
                "timestamp": int(time.time() * 1000)
            }
            params["sign"] = self.get_sign(params)
            res = self.session.post(url, data=params, headers=self.headers, timeout=30)
            data = res.json()

            if data.get("code") == 200:
                self.access_token = data["data"]["accessToken"]
                self.user_id = data["data"]["userId"]
                logger.info("✅ Zepp 官方登录成功")
                return True
            else:
                msg = data.get("msg", "无返回信息")
                logger.error(f"❌ 登录失败：{msg}")
                return False
        except Exception as e:
            logger.error(f"❌ 登录异常：{str(e)}")
            return False

    def upload_step(self, steps):
        """步数上报 完整参数"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            distance = round(steps * 0.68 / 1000, 2)
            calorie = round(steps * 0.038, 2)

            step_list = [{
                "date": today,
                "steps": steps,
                "distance": distance,
                "calories": calorie,
                "heartRate": 0
            }]

            url = f"{self.BASE_URL}/v1/step/upload"
            payload = {
                "userid": self.user_id,
                "access_token": self.access_token,
                "deviceid": self.device_id,
                "device_type": 1,
                "data_json": json.dumps(step_list, ensure_ascii=False)
            }
            res = self.session.post(url, json=payload, headers={
                "User-Agent": "ZeppLife/7.10.0",
                "Content-Type": "application/json"
            }, timeout=30)
            ret = res.json()
            if ret.get("code") == 200:
                logger.info(f"✅ 步数提交成功：{steps}")
                return True
            else:
                logger.error(f"❌ 步数提交失败：{ret.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ 上报异常：{str(e)}")
            return False

# ==================== 步数生成（不变） ====================
def get_current_steps(account_index=0):
    current_hour = datetime.now().hour
    closest_hour = None
    min_diff = float('inf')
    for hour in STEP_RANGES:
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

# ==================== 主程序 ====================
def main():
    logger.info("🎯 ZeppLife 原生新版API 任务启动")
    if not ACCOUNTS:
        logger.error("❌ 未读取到账号，退出")
        exit(1)
    success = 0
    fail = 0
    for idx, acc in enumerate(ACCOUNTS):
        logger.info(f"\n---------- 处理账号：{acc['username']} ----------")
        api = ZeppLifeApi()
        if not api.login(acc["username"], acc["password"]):
            fail += 1
            continue
        steps = get_current_steps(idx)
        if api.upload_step(steps):
            success += 1
        else:
            fail += 1
        if idx + 1 < len(ACCOUNTS):
            time.sleep(6)
    logger.info(f"\n========== 结束 ==========\n成功：{success} | 失败：{fail}")
    exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    main()
