@echo off
cd /d "C:\Users\suvam\Desktop\git_suvam\Jira_automation\email_scanner"
"C:\Users\suvam\AppData\Local\Programs\Python\Python311\python.exe" email_scanner.py --loop >> logs\email_scanner.log 2>&1
