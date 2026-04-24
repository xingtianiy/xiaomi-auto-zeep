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

# ========= 配置 =========
MAX_RETRY = 3
REQUEST_TIMEOUT = 20

PROXY = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

# ========= 账号 =========
def get_accounts():
    accs = []
    for i in range(1, 6):
        u = os.getenv(f'ACCOUNT{i}_USERNAME')
        p = os.getenv(f'ACCOUNT{i}_PASSWORD')
        if u and p:
            accs.append({"u": u, "p": p})
            logger.info(f"加载账号{i}: {u}")
    return accs

ACCOUNTS = get_accounts()

# ========= 步数 =========
STEP_RANGES = {
    8: (6000, 10000),
    12: (8000, 14000),
    16: (10000, 18000),
    20: (12000, 22000),
    22: (15000, 24000)
}

def gen_steps(idx):
    h = datetime.now().hour
    k = min(STEP_RANGES.keys(), key=lambda x: abs(x - h))
    base = random.randint(*STEP_RANGES[k]) if abs(k - h) <= 2 else 20000
    return max(1000, base + random.randint(-500, 500))

# ========= 客户端 =========
class Client:

    def __init__(self):
        self.s = requests.Session()
        self.proxies = {"http": PROXY, "https": PROXY} if PROXY else None

    def _post(self, url, data, headers, allow_redirects=True):
        return self.s.post(
            url,
            data=data,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=allow_redirects,
            proxies=self.proxies
        )

    # -------- 登录 --------
    def login(self, username, password):
        if username.isdigit():
            username = "+86" + username
            t = "huami_phone"
        elif "@" in username:
            t = "email"
        else:
            raise Exception("账号格式错误")

        headers = {
            "User-Agent": "MiFit/6.3.5 (iPhone; iOS 14.7.1)",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        for i in range(MAX_RETRY):
            try:
                logger.info(f"登录尝试 {i+1}")

                url = f"https://api-user.huami.com/registrations/{username}/tokens"
                data = {
                    "client_id": "HuaMi",
                    "password": password,
                    "redirect_uri": "https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html",
                    "token": "access",
                    "country_code": "CN"
                }

                resp = self._post(url, data, headers, allow_redirects=False)

                loc = resp.headers.get("Location", "")

                if "access=" not in loc:
                    logger.warning(f"无 access，可能风控: status={resp.status_code}")
                    time.sleep(2)
                    continue

                access = loc.split("access=")[-1].split("&")[0]

                url2 = "https://account.huami.com/v2/client/login"
                data2 = {
                    "app_name": "com.xiaomi.hm.health",
                    "app_version": "6.3.5",
                    "code": access,
                    "country_code": "CN",
                    "device_id": "123456",
                    "device_id_type": "uuid",
                    "grant_type": "access_token",
                    "third_name": t
                }

                r2 = self._post(url2, data2, headers)
                js = r2.json()

                if "token_info" not in js:
                    raise Exception("token_info缺失")

                return js["token_info"]["user_id"], js["token_info"]["app_token"]

            except Exception as e:
                logger.error(f"登录失败: {e}")
                time.sleep(2)

        raise Exception("登录最终失败")

    # -------- 提交 --------
    def submit(self, uid, token, steps):
        url = "https://api-mifit-cn2.huami.com/v1/data/band_data.json"

        payload = {
            "userid": uid,
            "last_sync_data_time": int(time.time()),
            "device_type": 0,
            "data_json": json.dumps([{
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data": [{"start": 0, "stop": 1439, "value": steps}]
            }])
        }

        headers = {
            "User-Agent": "MiFit/6.3.5",
            "apptoken": token,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        for i in range(MAX_RETRY):
            try:
                r = self._post(url, payload, headers)
                js = r.json()

                if js.get("message") == "success":
                    return True, "success"

                logger.warning(f"提交异常: {js}")
                time.sleep(2)

            except Exception as e:
                logger.error(f"提交异常: {e}")
                time.sleep(2)

        return False, "提交失败"

# ========= 主流程 =========
def run():
    if not ACCOUNTS:
        logger.error("无账号")
        return

    c = Client()
    ok = fail = 0

    for i, acc in enumerate(ACCOUNTS, 1):
        logger.info(f"处理账号{i}")

        try:
            if not re.match(r'^1[3-9]\d{9}$|^[^@]+@[^@]+\.[^@]+$', acc["u"]):
                raise Exception("账号格式错误")

            steps = gen_steps(i)
            logger.info(f"生成步数: {steps}")

            uid, token = c.login(acc["u"], acc["p"])
            logger.info(f"登录成功 uid={uid}")

            s, msg = c.submit(uid, token, steps)

            if s:
                ok += 1
                logger.info(f"提交成功 {steps}")
            else:
                fail += 1
                logger.error(msg)

        except Exception as e:
            fail += 1
            logger.error(f"失败: {e}")

        if i < len(ACCOUNTS):
            t = random.randint(3, 8)
            logger.info(f"等待{t}s")
            time.sleep(t)

    logger.info(f"完成 成功:{ok} 失败:{fail}")

# ========= 入口 =========
if __name__ == "__main__":
    run()
