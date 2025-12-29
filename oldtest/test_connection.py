#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前后端连接测试脚本
"""

import requests
import json
import time
import subprocess
import sys
import os
from threading import Thread

def test_backend_health():
    """测试后端健康检查"""
    try:
        response = requests.get('http://localhost:5000/api/health', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 后端健康检查通过: {data}")
            return True
        else:
            print(f"❌ 后端健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 后端连接失败: {e}")
        return False

def test_chat_api():
    """测试聊天API"""
    try:
        test_data = {
            "userInput": "你好，请介绍一下你自己",
            "useRag": False  # 先测试不使用RAG
        }
        
        response = requests.post(
            'http://localhost:5000/api/chat',
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 聊天API测试通过")
            print(f"   响应: {data.get('data', {}).get('answer', '')[:100]}...")
            return True
        else:
            print(f"❌ 聊天API测试失败: {response.status_code}")
            print(f"   错误: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 聊天API连接失败: {e}")
        return False

def test_frontend_proxy():
    """测试前端代理"""
    try:
        # 测试前端是否能通过代理访问后端
        response = requests.get('http://localhost:5173/api/health', timeout=5)
        if response.status_code == 200:
            print("✅ 前端代理工作正常")
            return True
        else:
            print(f"❌ 前端代理测试失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 前端代理连接失败: {e}")
        return False

def start_backend():
    """启动后端服务器"""
    print("🚀 启动后端服务器...")
    try:
        # 切换到工作目录
        os.chdir('/home/ubuntu/qj_temp/workflow_wxk')
        
        # 启动后端服务器
        process = subprocess.Popen([
            'python3', 'backend_server.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待服务器启动
        time.sleep(10)
        
        # 检查进程是否还在运行
        if process.poll() is None:
            print("✅ 后端服务器启动成功")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ 后端服务器启动失败")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return None
            
    except Exception as e:
        print(f"❌ 启动后端服务器时出错: {e}")
        return None

def main():
    """主测试函数"""
    print("🧪 前后端连接测试")
    print("=" * 50)
    
    # 检查后端是否已经在运行
    if test_backend_health():
        print("📡 后端服务器已在运行")
    else:
        print("📡 后端服务器未运行，尝试启动...")
        backend_process = start_backend()
        if not backend_process:
            print("❌ 无法启动后端服务器，测试终止")
            return
        
        # 等待服务器完全启动
        time.sleep(5)
        
        # 再次检查健康状态
        if not test_backend_health():
            print("❌ 后端服务器启动后仍无法连接")
            return
    
    print("\n🔍 测试聊天API...")
    test_chat_api()
    
    print("\n🌐 测试前端代理...")
    test_frontend_proxy()
    
    print("\n📋 测试总结:")
    print("1. 确保后端服务器在 http://localhost:5000 运行")
    print("2. 确保前端开发服务器在 http://localhost:5173 运行")
    print("3. 前端通过Vite代理访问后端API")
    print("4. 如果测试失败，请检查:")
    print("   - 后端服务器是否正常启动")
    print("   - 前端Vite配置是否正确")
    print("   - 网络连接是否正常")

if __name__ == "__main__":
    main()
