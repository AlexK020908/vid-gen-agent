import {continueRender, delayRender} from 'remotion';
import interUrl from './fonts/Inter.ttf';
import monoUrl from './fonts/JetBrainsMono.ttf';

// Inter and JetBrains Mono (both SIL Open Font License: fonts/OFL.txt, fonts/OFL-JetBrainsMono.txt), bundled so a
// render never depends on the machine's fonts. diagram/layout.py measures text with the same files.
export const FONT = 'Inter';
export const MONO = 'JetBrains Mono';

let loaded = false;

export const loadFonts = (): void => {
  if (loaded || typeof document === 'undefined') return;
  loaded = true;
  const faces: [string, string, string][] = [[FONT, interUrl, '100 900'], [MONO, monoUrl, '100 800']];
  for (const [family, url, weight] of faces) {
    const handle = delayRender(`Loading ${family}`);
    const face = new FontFace(family, `url(${url})`, {weight});
    face
      .load()
      .then((f) => {
        document.fonts.add(f);
        continueRender(handle);
      })
      .catch((err) => {
        console.error(`${family} failed to load`, err);
        continueRender(handle);
      });
  }
};
