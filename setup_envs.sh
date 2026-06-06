#!/bin/bash
echo "============================================="
echo "Creating Virtual Environments & Installing Requirements"
echo "============================================="

# Array of directories that contain requirements.txt
PARTS=("TrainingModel" "PipeLine" "RaspberryPi")

for PART in "${PARTS[@]}"; do
    if [ -d "$PART" ]; then
        echo ""
        echo "Setting up environment for: $PART"
        echo "---------------------------------------------"
        
        # Create virtual environment if it doesn't exist
        if [ ! -d "$PART/.venv" ]; then
            echo "Creating virtual environment in $PART/.venv..."
            python3 -m venv "$PART/.venv"
        else
            echo "Virtual environment already exists in $PART/.venv."
        fi
        
        # Install requirements
        if [ -f "$PART/requirements.txt" ]; then
            echo "Installing requirements from $PART/requirements.txt..."
            "$PART/.venv/bin/python" -m pip install --upgrade pip
            "$PART/.venv/bin/python" -m pip install -r "$PART/requirements.txt" --extra-index-url https://download.pytorch.org/whl/cpu
        else
            echo "Warning: No requirements.txt found in $PART"
        fi
    else
        echo "Warning: Directory $PART not found"
    fi
done

echo ""
echo "============================================="
echo "Virtual environments setup completed!"
echo "============================================="
