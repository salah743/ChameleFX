
# ChameleFX Surgical Batches (v2)

Drop these into `D:\ChameleFX\tools\patch_py2\` and run from project root:

```powershell
.\py-portable\python\python.exe .	ools\patch_py2\Batch_A_Security_Critical.py
.\py-portable\python\python.exe .	ools\patch_py2\Batch_B_Stability_Quality.py
```

Then start the API in foreground to see loader logs:

```powershell
.\py-portable\python\python.exe -m uvicorn app.api.server:app --host 127.0.0.1 --port 18124 --log-level debug
```
