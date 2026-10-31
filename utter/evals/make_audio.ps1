# Generate speech eval clips locally with Windows' built-in text-to-speech (no network).
# Usage (from utter/):  powershell -ExecutionPolicy Bypass -File evals\make_audio.ps1
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here 'audio'
New-Item -ItemType Directory -Force $outDir | Out-Null
$cases = Get-Content (Join-Path $here 'speech_cases.json') -Raw | ConvertFrom-Json

$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
Write-Output ("voice: " + $synth.Voice.Name)

foreach ($case in $cases) {
    $path = Join-Path $outDir ($case.id + '.wav')
    $synth.SetOutputToWaveFile($path, $format)
    $synth.Speak($case.say)
    $synth.SetOutputToNull()
    Write-Output ("wrote " + $path)
}
$synth.Dispose()
