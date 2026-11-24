param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$FindText,
    [Parameter(Mandatory = $true)][string]$ReplaceWith,
    [Parameter(Mandatory = $true)][string]$EvidencePath
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $systemUtility = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1'
    if (Test-Path -LiteralPath $systemUtility) { Import-Module -Name $systemUtility -Force -ErrorAction Stop }
}
if ($FindText -eq $ReplaceWith) { throw 'FindText and ReplaceWith must differ.' }
$word = $null
$document = $null
$copy = $null
function Get-TextHash([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::Unicode.GetBytes($Text)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
try {
    $source = (Resolve-Path -LiteralPath $Docx).Path
    $sourceBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    $copy = Join-Path ([System.IO.Path]::GetTempPath()) ("resume-edit-undo-" + [Guid]::NewGuid().ToString('N') + '.docx')
    Copy-Item -LiteralPath $source -Destination $copy
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($copy, $false, $false)
    $document.Repaginate()
    $pagesBefore = $document.ComputeStatistics(2)
    $beforeText = $document.Content.Text
    $beforeHash = Get-TextHash $beforeText
    $find = $document.Content.Find
    $find.ClearFormatting()
    $find.Replacement.ClearFormatting()
    $replaced = $find.Execute($FindText, $false, $false, $false, $false, $false, $true, 1, $false, $ReplaceWith, 2)
    if (-not $replaced) { throw "Find text not found: $FindText" }
    $replacementCount = 1
    $duringHash = Get-TextHash $document.Content.Text
    if ($duringHash -eq $beforeHash) { throw 'Text hash did not change after replacement.' }
    $document.Undo(1)
    $undoCount = 1
    $document.Repaginate()
    $pagesAfter = $document.ComputeStatistics(2)
    $afterHash = Get-TextHash $document.Content.Text
    if ($afterHash -ne $beforeHash) { throw 'Text hash did not recover after undo.' }
    if ($pagesAfter -ne $pagesBefore) { throw "Page count changed after undo: $pagesBefore to $pagesAfter" }
    $document.Close($false)
    $document = $null
    $word.Quit()
    $word = $null
    $sourceAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if ($sourceAfter -ne $sourceBefore) { throw 'Source DOCX hash changed.' }
    $result = [ordered]@{
        exporter = 'Microsoft.Office.Interop.Word'
        source = $source
        temp_copy = $true
        before_sha256 = $beforeHash
        during_sha256 = $duringHash
        after_sha256 = $afterHash
        replacement_count = $replacementCount
        undo_count = $undoCount
        pages_before = $pagesBefore
        pages_after = $pagesAfter
        saved = $false
        source_unchanged = $true
        timestamp = [DateTimeOffset]::Now.ToString('o')
    }
    $json = $result | ConvertTo-Json -Depth 4
    $evidence = [System.IO.Path]::GetFullPath($EvidencePath)
    [System.IO.File]::WriteAllText($evidence, $json, [System.Text.UTF8Encoding]::new($false))
    [Console]::Out.Write($json)
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
    if ($copy -and (Test-Path -LiteralPath $copy)) { Remove-Item -LiteralPath $copy -Force -ErrorAction SilentlyContinue }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
