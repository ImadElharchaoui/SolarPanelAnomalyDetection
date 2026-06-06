@echo off
echo =============================================
echo Creating Virtual Environments ^& Installing Requirements
echo =============================================

:: List of folders containing requirements.txt
set folders=TrainingModel PipeLine RaspberryPi

for %%f in (%folders%) do (
    if exist %%f (
        echo.
        echo Setting up environment for: %%f
        echo ---------------------------------------------
        
        :: Create virtual environment if it doesn't exist
        if not exist %%f\.venv (
            echo Creating virtual environment in %%f\.venv...
            python -m venv %%f\.venv
        ) else (
            echo Virtual environment already exists in %%f\.venv.
        )
        
        :: Install requirements
        if exist %%f\requirements.txt (
            echo Installing requirements from %%f\requirements.txt...
            %%f\.venv\Scripts\python -m pip install --upgrade pip
            %%f\.venv\Scripts\python -m pip install -r %%f\requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
        ) else (
            echo Warning: No requirements.txt found in %%f
        )
    ) else (
        echo Warning: Directory %%f not found
    )
)

echo.
echo =============================================
echo Virtual environments setup completed!
echo =============================================
pause
