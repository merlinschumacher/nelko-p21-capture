# nelko-p21-capture
This is a capture of the bluetooth traffic of a Nelko P21 label printer

It contains a connection and a print of the default template on a 14x40mm label. The printer itself uses some proprietary commands like:
- `BATTERY?`  
  Responds with: `BATTERY ` followed by two bytes. 
  In this capture it's 0x99 and 0x00. It was charged more than 99% at this point, I believe.
- `CONFIG?` 
  Responds with: `CONFIG ` followed by `00cb00000304020402010d0a`. 
  The first byte may indicate some protocol type, in this case TSPL2 and the second to the DPI resolution of 203 (CB).
  000003 corresponds to the first firmware version in the app (0.3.0).
  040204 corresponds to the second firmware version in the app (4.2.4).
  0201 at the end is unknown. It might be the automatic timeout and the beep feature.
- `[ESC]!0`  
  Purpose unknown

The sent printing commands correspond to TSPL2:
```
SIZE 14.0 mm,40.0 mm
GAP 5.0 mm,0 mm
DIRECTION 0,0
DENSITY 15
CLS
BITMAP 0,0,12,284,1,?????AT???GuC??
... [truncated]
```

The printer also exposes a serial USB connection to the PC but only returns `ERROR0` on any command. 

Internally it uses a JieLi AC6951C (or similiar) bluetooth chip (see https://github.com/kagaimiq/jielie/pull/6).

Nelkos app also uses JieLis ota update feature. It checks for updates at this url: http://app.nelko.net/api/firmware/verify with a POST request:

```json
{"hardwareName":"0.0.3","dev":"P21","firmwareName":"4.2.4"}
```

There seems to be no way to get the URL for the current firmware. The app is very chatty and even sends the entire device metadata to the server. And seemingly via plain HTTP.
