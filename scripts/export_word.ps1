param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf
)

$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {
    $docxFull = (Resolve-Path -LiteralPath $Docx).Path
    $pdfFull = [System.IO.Path]::GetFullPath($Pdf)
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $engineVersion = $word.Version
    # ReadOnly：分页和域更新只发生在内存，不回写用户 DOCX。
    $document = $word.Documents.Open($docxFull, $false, $true)
    $document.Repaginate()
    # 17 = wdExportFormatPDF。必须由 Word 自己导出，不能替换为 Print to PDF。
    $document.ExportAsFixedFormat($pdfFull, 17)
    $document.Close($false)
    $document = $null
    $word.Quit()
    $word = $null
    if (-not (Test-Path -LiteralPath $pdfFull)) { throw "Word 未生成 PDF：$pdfFull" }
    $item = Get-Item -LiteralPath $pdfFull
    if ($item.Length -lt 1000) { throw "Word 生成的 PDF 异常：$($item.Length) 字节" }
    [pscustomobject]@{ Pdf = $item.FullName; Bytes = $item.Length; Engine = $engineVersion }
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
