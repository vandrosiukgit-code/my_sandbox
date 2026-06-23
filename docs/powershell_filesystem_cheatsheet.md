# PowerShell filesystem cheatsheet

## Navigation

Show current directory:

```powershell
pwd
```

Go to project root:

```powershell
cd C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox
```

Go one level up:

```powershell
cd ..
```

## Listing files

Show files and folders:

```powershell
ls
```

Show files and folders, including hidden items:

```powershell
ls -Force
```

## Create folders

Create a folder:

```powershell
mkdir fixtures\actions
```

## Read files

Print a file:

```powershell
Get-Content fixtures\action_runner.py
```

Print first lines of a file:

```powershell
Get-Content fixtures\action_runner.py -TotalCount 40
```

## Find files

Find files by name:

```powershell
Get-ChildItem -Recurse -Filter action_runner.py
```

## Search text

Search text in the project:

```powershell
rg "player_card_play"
```

## Run action runner

From the project root:

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py list
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py run player_card_play
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py run 1
```

Interactive mode:

```powershell
& ".\.venv\Scripts\python.exe" fixtures\action_runner.py
```

Inside the prompt:

```text
list
run 1
reload
quit
```

`reload` restarts the last action process while the prompt stays open.
