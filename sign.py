import requests
import json
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ================== 读取 Secrets ==================

config = json.loads(os.environ["USER_JSON"])

OPEN_ID = config["OPEN_ID"]
LOCATION_INFO = config["LOCATION_INFO"]
PUSHPLUS_TOKEN = config["PUSHPLUS_TOKEN"]
PUSHPLUS_URL = config["PUSHPLUS_URL"]

# ================== 配置区 ==================

QD_HEADERS = {
    "authority": "qfhy.suse.edu.cn",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://qfhy.suse.edu.cn",
    "referer": f"https://qfhy.suse.edu.cn/xg/app/qddk/admin?open_id={OPEN_ID}",
    "user-agent": "Mozilla/5.0"
}

QD_URL = "https://qfhy.suse.edu.cn/site/qddk/qdrw/api/checkSignLocationWithPhoto.rst"


# ================== 工具函数 ==================

def get_session(open_id: str) -> str:
    """使用 Playwright 获取 SESSION"""

    with sync_playwright() as p:

        browser = p.firefox.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(
            f"https://qfhy.suse.edu.cn/xg/app/qddk/admin?open_id={open_id}"
        )

        page.wait_for_timeout(5000)

        cookies = context.cookies()

        session = ""

        for cookie in cookies:
            if cookie["name"] == "SESSION":
                session = cookie["value"]

        browser.close()

        print(f"获取到SESSION: {session}")

        return session


def init_cookies(session: str) -> dict:
    """初始化 Cookie"""

    return {
        "SESSION": session
    }


def get_task_info(cookies: dict) -> dict:
    """获取待签到任务"""

    headers = {
        "authority": "qfhy.suse.edu.cn",
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "Content-Type": "undefined",
        "appCode": "qddk",
        "referer": f"https://qfhy.suse.edu.cn/xg/app/qddk/admin?open_id={OPEN_ID}",
        "user-agent": QD_HEADERS["user-agent"]
    }

    list_url = "https://qfhy.suse.edu.cn/site/qddk/qdrw/api/myList.rst"

    params = {"status": 1}

    try:

        response = requests.get(
            list_url,
            headers=headers,
            cookies=cookies,
            params=params,
            timeout=10
        )

        data = response.json()

        if not data.get("success") and "系统未找到你的身份信息" in data.get("errorMsg", ""):
            return {"status": "Cookie失效"}

        task_list = data.get("result", {}).get("data", [])

        return task_list[0] if task_list else None

    except Exception as e:

        print(f"获取任务失败: {e}")

        return None


def sign_task(task_info: dict, cookies: dict, location_info: dict) -> dict:
    """执行签到"""

    if not task_info:

        return {"success": False, "msg": "没有找到待签到任务", "qd_id": "0000"}

    qd_id = task_info.get("id")

    payload = {
        "id": qd_id,
        "qdzt": 1,
        "qdsj": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
        "isOuted": location_info["isOuted"],
        "isLated": location_info["isLated"],
        "qdddjtdz": location_info["location"]["address"],
        "location": json.dumps(location_info["location"], ensure_ascii=False),
        "dkddPhoto": "",
        "fwwsy": "",
        "cdsy": "",
        "txxx": "{}"
    }

    try:

        response = requests.post(
            QD_URL,
            json=payload,
            headers=QD_HEADERS,
            cookies=cookies,
            timeout=10
        )

        data = response.json()

        if not data.get("success") and "系统未找到你的身份信息" in data.get("errorMsg", ""):

            return {"success": False, "msg": "Cookie失效", "qd_id": qd_id}

        return {"success": True, "msg": response.text, "qd_id": qd_id}

    except Exception as e:

        return {"success": False, "msg": str(e), "qd_id": qd_id}


def push_message(token: str, title: str, content: str):
    """PushPlus 推送"""

    data = {
        "token": token,
        "title": title,
        "content": content
    }

    try:
        requests.post(PUSHPLUS_URL, data=data, timeout=5)
    except Exception:
        pass


def format_content(result: dict, cookies: dict) -> str:
    """保持原来的推送格式"""

    qd_id_text = f"签到任务ID: {result.get('qd_id')}\n"

    cookie_text = "当前Cookie:\n" + "\n".join(
        f"{k}={v}" for k, v in cookies.items()
    )

    return (
        f"签到时间: {(datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{qd_id_text}"
        f"签到结果:\n{result['msg']}\n\n"
        f"{cookie_text}"
    )


# ================== 主程序 ==================

def main():

    session = get_session(OPEN_ID)

    cookies = init_cookies(session)

    task_info = get_task_info(cookies)

    result = sign_task(task_info, cookies, LOCATION_INFO)

    title = "今日打卡结果 ✅" if result["success"] else "今日打卡失败 ❌"

    content = format_content(result, cookies)

    push_message(PUSHPLUS_TOKEN, title, content)

    print(title)
    print(content)


if __name__ == "__main__":
    main()
