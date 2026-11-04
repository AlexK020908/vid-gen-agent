import {continueRender, delayRender} from 'remotion';
import interUrl from './fonts/Inter.ttf';

// Inter (SIL Open Font License, fonts/OFL.txt), bundled so a render never depends on the machine's fonts
export const FONT = 'Inter';

let loaded = false;

export const loadFonts = (): void => {
  if (loaded || typeof document === 'undefined') return;
  loaded = true;
  const handle = delayRender('Loading Inter');
  const face = new FontFace(FONT, `url(${interUrl})`, {weight: '100 900'});
  face
    .load()
    .then((f) => {
      document.fonts.add(f);
      continueRender(handle);
    })
    .catch((err) => {
      console.error('Inter failed to load', err);
      continueRender(handle);
    });
};
