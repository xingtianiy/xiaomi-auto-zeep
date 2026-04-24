#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import random
import time
import json
import logging
from datetime import datetime
import os
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 账号配置 ====================
def get_accounts_from_env():
    accounts = []
    for i in range(1, 6):
        username = os.getenv(f'ACCOUNT{i}_USERNAME')
        password = os.getenv(f'ACCOUNT{i}_PASSWORD')
        if username and password:
            accounts.append({"username": username, "password": password})
            logger.info(f"✅ 加载账号 {i}: {username}")
    if not accounts:
        logger.warning("⚠️ 未找到账号配置")
    return accounts

ACCOUNTS = get_accounts_from_env()

# ==================== 步数规则 ====================
STEP_RANGES = {
    8: {"min": 6000, "max": 10000},
    12: {"min": 8000, "max": 14000},
    16: {"min": 10000, "max": 18000},
    20: {"min": 12000, "max": 22000},
    22: {"min": 15000, "max": 24000}
}

DEFAULT_STEPS = 20000

# ==================== 核心类 ====================
class XiaomiClient:

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    # ================= 登录 =================
    def login(self, username, password):
        if username.isdigit():
            username_type = "huami_phone"
            username = "+86" + username
        elif "@" in username:
            username_type = "email"
        else:
            raise Exception("账号格式错误")

        # Step1 获取 access
        url = f"https://api-user.huami.com/registrations/{username}/tokens"
        data = {
            "client_id": "HuaMi",
            "password": password,
            "redirect_uri": "https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html",
            "token": "access"
        }

        resp = self.session.post(url, data=data, allow_redirects=False)

        location = resp.headers.get("Location", "")
        if "access=" not in location:
            raise Exception("登录失败")

        access = location.split("access=")[-1].split("&")[0]

        # Step2 换 token
        url2 = "https://account.huami.com/v2/client/login"
        data2 = {
            "app_name": "com.xiaomi.hm.health",
            "app_version": "6.3.5",
            "code": access,
            "country_code": "CN",
            "device_id": "123456",
            "device_id_type": "uuid",
            "grant_type": "access_token",
            "third_name": username_type
        }

        resp2 = self.session.post(url2, data=data2)
        result = resp2.json()

        if "token_info" not in result:
            raise Exception("获取 token 失败")

        return result["token_info"]["user_id"], result["token_info"]["app_token"]

    # ================= 提交步数 =================
    def submit_steps(self, user_id, app_token, steps):
        url = "https://api-mifit-cn2.huami.com/v1/data/band_data.json"

        today = datetime.now().strftime("%Y-%m-%d")
        now_ts = int(time.time())

        data_json = [{
            "date": today,
            "data": [{
                "start": 0,
                "stop": 1439,
                "value": steps
            }]
        }]

        payload = {
            "userid": user_id,
            "last_sync_data_time": now_ts,
            "device_type": 0,
            "data_json": json.dumps(data_json)
        }

        headers = {
            "apptoken": app_token,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        resp = self.session.post(url, data=payload, headers=headers)

        try:
            result = resp.json()
        except:
            return False, "返回解析失败"

        if result.get("message") == "success":
            return True, "提交成功"
        else:
            return False, str(result)

# ==================== 主逻辑 ====================
class StepSubmitter:

    def get_steps(self, index):
        hour = datetime.now().hour

        closest = min(STEP_RANGES.keys(), key=lambda x: abs(x - hour))
        config = STEP_RANGES.get(closest)

        if config and abs(closest - hour) <= 2:
            base = random.randint(config["min"], config["max"])
        else:
            base = DEFAULT_STEPS

        return max(1000, base + random.randint(-500, 500))

    def validate(self, username, password):
        phone = r'^1[3-9]\d{9}$'
        email = r'^[^@]+@[^@]+\.[^@]+$'

        if not username or not password:
            return False, "账号或密码为空"

        if " " in password:
            return False, "密码含空格"

        if re.match(phone, username) or re.match(email, username):
            return True, "OK"

        return False, "账号格式错误"

    def run(self):
        if not ACCOUNTS:
            logger.error("❌ 没账号")
            return

        success = 0
        fail = 0

        client = XiaomiClient()

        for i, acc in enumerate(ACCOUNTS, 1):
            logger.info(f"🔄 账号 {i}: {acc['username']}")

            ok, msg = self.validate(acc["username"], acc["password"])
            if not ok:
                logger.error(msg)
                fail += 1
                continue

            try:
                steps = self.get_steps(i)

                user_id, token = client.login(acc["username"], acc["password"])
                logger.info(f"🔑 登录成功 user_id={user_id}")

                ok, msg = client.submit_steps(user_id, token, steps)

                if ok:
                    success += 1
                    logger.info(f"✅ 步数 {steps}")
                else:
                    fail += 1
                    logger.error(f"❌ {msg}")

            except Exception as e:
                fail += 1
                logger.error(f"异常: {str(e)}")

            if i < len(ACCOUNTS):
                time.sleep(5)

        logger.info(f"🏁 完成 成功:{success} 失败:{fail}")

# ==================== 入口 ====================
if __name__ == "__main__":
    StepSubmitter().run()
