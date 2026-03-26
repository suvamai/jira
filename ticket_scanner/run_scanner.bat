@echo off
cd /d "C:\Users\suvam\Desktop\git_suvam\Jira_automation\ticket_scanner"
"C:\Users\suvam\AppData\Local\Programs\Python\Python311\python.exe" ticket_scanner.py >> logs\scanner.log 2>&1
