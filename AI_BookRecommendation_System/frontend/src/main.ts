import { enableProdMode } from '@angular/core';
import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';

import { AppModule } from './app/app.module';
import { environment } from './environments/environment';

// Enable production mode if environment is set to production
if (environment.production) {
  enableProdMode();
}

// Bootstrap the main AppModule to launch the Angular app
platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err)); // Log any bootstrapping errors
