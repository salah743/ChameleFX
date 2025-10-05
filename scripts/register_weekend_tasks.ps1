# Refactored script to register weekly scheduled tasks in local time (Asia/Dubai).
# This version defines common variables and settings only once to reduce redundancy.

# ====================================
# 1. GLOBAL CONFIGURATION & COMMON SETTINGS
# ====================================

# Define the PowerShell executable path
$PS = "powershell.exe"

# Define common arguments for running scripts
$PS_ARGS_TEMPLATE = "-NoProfile -ExecutionPolicy Bypass -File `"{0}`""

# Define common task settings: wake if needed, allow on AC only (adjust to taste)
$CommonSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

# Helper function to create the scheduled task action
function New-ChameleFxTaskAction {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ScriptPath
    )
    $arguments = $PS_ARGS_TEMPLATE -f $ScriptPath
    return New-ScheduledTaskAction -Execute $PS -Argument $arguments
}

# Helper function to register a task
function Register-ChameleFxTask {
    param(
        [Parameter(Mandatory=$true)]
        [string]$TaskName,
        [Parameter(Mandatory=$true)]
        $Action,
        [Parameter(Mandatory=$true)]
        $Trigger
    )
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $CommonSettings `
        -Force
}

# ====================================
# 2. VALIDATION JOBS (Sat 01:10, Sun 01:10, Mon 00:55)
# ====================================
$SCRIPT = "D:\ChameleFX\scripts\weekend_validation.ps1"
$ActionValidation = New-ChameleFxTaskAction -ScriptPath $SCRIPT

# Validation Triggers
# Sat 01:10 – parity + slippage
$trigSat = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 1:10am
# Sun 01:10 – slippage refresh
$trigSun = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday   -At 1:10am
# Mon 00:55 – pre-open warmup (optional)
$trigMon = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday   -At 0:55am

# Register Validation Tasks
Register-ChameleFxTask -TaskName "ChameleFX_Weekend_Sat"     -Action $ActionValidation -Trigger $trigSat
Register-ChameleFxTask -TaskName "ChameleFX_Weekend_Sun"     -Action $ActionValidation -Trigger $trigSun
Register-ChameleFxTask -TaskName "ChameleFX_Weekend_PreOpen" -Action $ActionValidation -Trigger $trigMon

# ====================================
# 3. FEEDBACK JOBS (Sat 01:15, Sun 01:15)
# ====================================
$FB = "D:\ChameleFX\scripts\weekend_feedback.ps1"
$ActionFeedback = New-ChameleFxTaskAction -ScriptPath $FB

# Feedback Triggers (Dubai weekend times: after the 01:10 validation jobs)
$trigSatFB = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 1:15am
$trigSunFB = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday   -At 1:15am

# Register Feedback Tasks
Register-ChameleFxTask -TaskName "ChameleFX_Weekend_FB_Sat" -Action $ActionFeedback -Trigger $trigSatFB
Register-ChameleFxTask -TaskName "ChameleFX_Weekend_FB_Sun" -Action $ActionFeedback -Trigger $trigSunFB

# ====================================
# 4. SUMMARY
# ====================================
Write-Host "Successfully registered all weekend tasks:"
Write-Host "  - ChameleFX_Weekend_Sat     (Sat 01:10) [Validation]"
Write-Host "  - ChameleFX_Weekend_Sun     (Sun 01:10) [Validation]"
Write-Host "  - ChameleFX_Weekend_PreOpen (Mon 00:55) [Validation]"
Write-Host "  - ChameleFX_Weekend_FB_Sat  (Sat 01:15) [Feedback]"
Write-Host "  - ChameleFX_Weekend_FB_Sun  (Sun 01:15) [Feedback]"
