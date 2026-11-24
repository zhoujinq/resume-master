param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf,
    [string]$RepeatPdf,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $systemUtility = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1'
    if (Test-Path -LiteralPath $systemUtility) { Import-Module -Name $systemUtility -Force -ErrorAction Stop }
}
$word = $null
$document = $null
try {
    $docxFull = (Resolve-Path -LiteralPath $Docx).Path
    $pdfFull = [System.IO.Path]::GetFullPath($Pdf)
    $repeatFull = if ($RepeatPdf) { [System.IO.Path]::GetFullPath($RepeatPdf) } else { $null }
    if (-not $LogPath) { $LogPath = [System.IO.Path]::ChangeExtension($pdfFull, '.word-export.json') }
    $logFull = [System.IO.Path]::GetFullPath($LogPath)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $engineVersion = $word.Version
    $document = $word.Documents.Open($docxFull, $false, $true)
    $document.Repaginate()
    # 17 = wdExportFormatPDF. Same Word instance and same open document.
    $document.ExportAsFixedFormat($pdfFull, 17)
    if (-not (Test-Path -LiteralPath $pdfFull)) { throw "First Word export missing: $pdfFull" }
    if ($repeatFull) {
        $document.ExportAsFixedFormat($repeatFull, 17)
        if (-not (Test-Path -LiteralPath $repeatFull)) { throw "Second Word export missing: $repeatFull" }
    }
    $document.Close($false)
    $document = $null
    $word.Quit()
    $word = $null
    foreach ($target in @($pdfFull) + @($repeatFull)) {
        if (-not $target) { continue }
        $item = Get-Item -LiteralPath $target
        if ($item.Length -lt 1000) { throw "Word PDF is too small: $target" }
    }
    $result = [ordered]@{
        exporter = 'Microsoft.Office.Interop.Word'
        engine_version = $engineVersion
        input = $docxFull
        output = $pdfFull
        repeat_output = $repeatFull
        exit_code = 0
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $pdfFull).Hash.ToLowerInvariant()
        repeat_sha256 = if ($repeatFull) { (Get-FileHash -Algorithm SHA256 -LiteralPath $repeatFull).Hash.ToLowerInvariant() } else { $null }
        timestamp = [DateTimeOffset]::Now.ToString('o')
    }
    $json = $result | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($logFull, $json, [System.Text.UTF8Encoding]::new($false))
    [Console]::Out.Write($json)
}
catch {
    if ($LogPath) {
        $failure = [ordered]@{ exporter = 'Microsoft.Office.Interop.Word'; input = $Docx; output = $Pdf; exit_code = 1; error = $_.Exception.Message }
        [System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($LogPath), ($failure | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
    }
    throw
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch {}
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
