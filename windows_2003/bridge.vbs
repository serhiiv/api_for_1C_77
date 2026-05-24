' bridge.vbs
' Runs 1C:Enterprise 7.7 and returns full path to output JSON file.
' Arguments:
'   0 - input JSON file path
'   1 - Path_1C
'   2 - User_1C
'   3 - Pass_1C

Option Explicit

Dim args
Dim strInputFile
Dim Path_1C
Dim User_1C
Dim Pass_1C
Dim fso
Dim oneC
Dim connectionString
Dim res
Dim evalExpr
Dim strResultFile

Set args = WScript.Arguments

If args.Count < 4 Then
    WScript.Echo "Error: Usage bridge.vbs <input_json> <Path_1C> <User_1C> <Pass_1C>"
    WScript.Quit 1
End If

strInputFile = Trim(args(0))
Path_1C = Trim(args(1))
User_1C = Trim(args(2))
Pass_1C = Trim(args(3))

Set fso = CreateObject("Scripting.FileSystemObject")

If Not fso.FileExists(strInputFile) Then
    WScript.Echo "Error: Input file not found: " & strInputFile
    WScript.Quit 1
End If

strInputFile = fso.GetAbsolutePathName(strInputFile)

On Error Resume Next

' 1. Ініціалізація 1С 7.7
Err.Clear
Set oneC = CreateObject("V77.Application")
If Err.Number <> 0 Or TypeName(oneC) = "Nothing" Then
    WScript.Echo "Error: Cannot create V77.Application: " & Err.Description & " (Err=" & CStr(Err.Number) & ")"
    WScript.Quit 1
End If

connectionString = "/D""" & Path_1C & """ /N""" & User_1C & """ /P""" & Pass_1C & """"
res = oneC.Initialize(oneC.RMTrade, connectionString, "NO_SPLASH_SHOW")

If Not res Then
    WScript.Echo "Error: 1C Initialization failed."
    WScript.Quit 1
End If

If Err.Number <> 0 Then
    WScript.Echo "Error: 1C Initialize exception: " & Err.Description
    WScript.Quit 1
End If

' 2. Викликаємо api_worker і отримуємо шлях до вихідного файлу
' Передаємо шлях у 1С, вона повертає шлях до створеного _out.json
' Use ASCII function name to avoid codepage-related corruption in VBScript/CScript.
' Для імені функції використовується ASCII, щоб уникнути помилки з кодовою сторінкою, у VBScript/CScript.
evalExpr = "api_worker(" & Chr(34) & Replace(strInputFile, Chr(34), Chr(34) & Chr(34)) & Chr(34) & ")"
strResultFile = oneC.EvalExpr(evalExpr)

If Err.Number <> 0 Then
    WScript.Echo "Error: EvalExpr failed: " & Err.Description
    WScript.Quit 1
End If

strResultFile = Trim(CStr(strResultFile))
If strResultFile = "" Then
    WScript.Echo "Error: 1C returned empty output file path."
    WScript.Quit 1
End If

If Not fso.FileExists(strResultFile) Then
    WScript.Echo "Error: Output file not found: " & strResultFile
    WScript.Quit 1
End If

WScript.Echo fso.GetAbsolutePathName(strResultFile)
WScript.Quit 0
