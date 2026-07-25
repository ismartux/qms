import json
import re
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *

import os

LARK_APP_ID = os.getenv("LARK_APP_ID", "cli_a83144a175fad00c")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET", "")

# SDK 使用说明: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development
# 以下示例代码默认根据文档示例值填充，如果存在代码问题，请在 API 调试台填上相关必要参数后再复制代码使用
# 复制该 Demo 后, 需要将 "YOUR_APP_ID", "YOUR_APP_SECRET" 替换为自己应用的 APP_ID, APP_SECRET.
def extract_app_token(base_url: str):
    """
    Extract app_token from Feishu base URL
    """
    match = re.search(r'/base/([a-zA-Z0-9]+)', base_url)
    if not match:
        raise ValueError("Invalid Feishu Base URL")
    return match.group(1)


def main():
    # 🔹 Ask user for Base URL
    base_url = input("Enter Feishu Base URL: ").strip()

    try:
        app_token = extract_app_token(base_url)
    except ValueError as e:
        print("Error:", e)
        return

    print("Extracted App Token:", app_token)
    print("-" * 50)

    # 🔹 Create client
    client = lark.Client.builder() \
        .app_id(LARK_APP_ID) \
        .app_secret(LARK_APP_SECRET) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    page_token = None

    while True:
        builder = ListAppTableRequest.builder() \
            .app_token(app_token) \
            .page_size(50)

        if page_token:
            builder = builder.page_token(page_token)

        request = builder.build()

        response = client.bitable.v1.app_table.list(request)

        if not response.success():
            print("Error:", response.code, response.msg)
            return

        data = response.data

        # 🔹 Print tables
        for table in data.items:
            print("Table Name :", table.name)
            print("Table ID   :", table.table_id)
            print("-" * 40)

        if not data.has_more:
            break

        page_token = data.page_token


if __name__ == "__main__":
    main()