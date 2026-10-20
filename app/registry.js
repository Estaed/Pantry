/* Pantry feature registry. Add a feature by appending one line at the end:
     PANTRY_FEATURES.push('app/<feature>.js');
   Nothing else goes in this file: index.html loads it before app/core.js, which loads the features in this
   order, and sw.js runs it too (importScripts) to keep every listed feature available offline. */
self.PANTRY_FEATURES = [];
PANTRY_FEATURES.push('app/today.js');
PANTRY_FEATURES.push('app/log.js');
PANTRY_FEATURES.push('app/scan.js');
