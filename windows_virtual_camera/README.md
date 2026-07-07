\# CamComposite Virtual Camera



Windows DirectShow virtual camera backend.



Goal:

\- Register as "CamComposite Virtual Camera"

\- Receive frames from windows\_engine

\- Expose 1920x1080@30 output to Zoom/Meet/Teams



Implementation checkpoints:

1\. Build/register DirectShow source filter

2\. Output test pattern

3\. Read latest composed frame from shared memory

4\. Package DLL registration in Windows installer

