import os
import json
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ================== 环境变量 ==================

OPEN_ID = os.getenv("OPEN_ID")
LOCATION_POINT = os.getenv("LOCATION_POINT")
LOCATION_ADDRESS = os.getenv("LOCATION_ADDRESS")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")
PUSHPLUS_URL = os.getenv("PUSHPLUS_URL", "http://www.pushplus.plus/send")

if not OPEN_ID:
    raise ValueError("OPEN_ID 未设置")

# 解析坐标
POINT = [float(x) for x in LOCATION_POINT.split(",")]

LOCATION_INFO = {
    "isOuted": 0,
    "isLated": 0,
    "location": {
        "point": POINT,
        "address": LOCATION_ADDRESS
    }
}

QD_URL = "https://qfhy.suse.edu.cn/site/qddk/qdrw/api/checkSignLocationWithPhoto.rst"

BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://qfhy.suse.edu.cn",
    "referer": f"https://qfhy.suse.edu.cn/xg/app/qddk/admin?open_id={OPEN_ID}",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


# ================== Playwright 获取 SESSION ==================

def get_session():
    print("正在获取 SESSION ...")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context()

        page = context.new_page()

        page.goto(
            f"https://qfhy.suse.edu.cn/xg/app/qddk/admin?open_id={OPEN_ID}",
            wait_until="networkidle"
        )

        page.wait_for_timeout(3000)

        cookies = context.cookies()

        browser.close()

        for c in cookies:
            if c["name"] == "SESSION":
                print("SESSION 获取成功")
                return c["value"]

        raise Exception("未获取到 SESSION")


# ================== 初始化 Cookies ==================

def init_cookies(session):

    return {
        "_sop_session_": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIiLCJpYXQiOjE3NzM5MTg3MjksInVpZCI6IjIzMTA0MDcwNDA1IiwiaGlkIjowLCJhbGlhcyI6IiIsImNuIjoiIiwidGlja2V0IjoiMjVjZjA1ZjllNzhlZmQ1ZWY3NjJkNWI0NzNhZjg3MDAiLCJleHRyYSI6IntcImdyb3VwTmFtZVwiOlwiXCIsXCJpZGVudGl0eVR5cGVcIjoxLFwib3BlbklkXCI6XCJvWExfeDZ0MmdYOXFUUHRZYkZaRFN3WW5iLUlnXCIsXCJ5YkNsaWVudElkXCI6XCJHRzlBczF3aWRNMTkxMjAxXCJ9IiwiZXhwIjoxNzczOTU0NzI5fQ.XpnUj_mjXSRuBA96YL6_US70astdZLGnx2l2MhB-R5Q",
        "SESSION": session
    }


# ================== 获取任务 ==================

def get_task_info(cookies):

    print("获取签到任务...")

    url = "https://qfhy.suse.edu.cn/site/qddk/qdrw/api/myList.rst"

    headers = BASE_HEADERS.copy()
    headers["Content-Type"] = "undefined"
    headers["appCode"] = "qddk"

    params = {"status": 1}

    r = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=15)

    data = r.json()

    if not data.get("success"):
        print("接口返回失败:", data)
        return None

    tasks = data.get("result", {}).get("data", [])

    if not tasks:
        print("没有待签到任务")
        return None

    task = tasks[0]

    print("任务ID:", task["id"])

    return task


# ================== 执行签到 ==================

def sign(task, cookies):

    if not task:
        return {"success": False, "msg": "没有签到任务"}

    payload = {
        "id": task["id"],
        "qdzt": 1,
        "qdsj": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "isOuted": LOCATION_INFO["isOuted"],
        "isLated": LOCATION_INFO["isLated"],
        "qdddjtdz": LOCATION_INFO["location"]["address"],
        "location": json.dumps(LOCATION_INFO["location"], ensure_ascii=False),
        "dkddPhoto": "",
        "fwwsy": "",
        "cdsy": "",
        "txxx": "{}",
    }

    r = requests.post(
        QD_URL,
        headers=BASE_HEADERS,
        cookies=cookies,
        json=payload,
        timeout=15
    )

    try:
        data = r.json()
    except:
        data = {"raw": r.text}

    return data


# ================== PushPlus 推送 ==================

def push(title, content):

    if not PUSHPLUS_TOKEN:
        return

    try:
        requests.post(
            PUSHPLUS_URL,
            data={
                "token": PUSHPLUS_TOKEN,
                "title": title,
                "content": content
            },
            timeout=10
        )
    except Exception as e:
        print("PushPlus推送失败:", e)


# ================== 主函数 ==================

def main():

    try:

        session = get_session()

        cookies = init_cookies(session)

        task = get_task_info(cookies)

        result = sign(task, cookies)

        title = "签到成功 ✅" if result.get("success") else "签到失败 ❌"

        content = f"""
时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
任务ID:{task['id']}
success: {result['success']}
签到信息: {result['msg']}

SESSION:
{session}
"""

        print(content)

        push(title, content)

    except Exception as e:

        err = f"签到异常: {str(e)}"

        print(err)

        push("签到脚本异常 ❌", err)


if __name__ == "__main__":
    main()
