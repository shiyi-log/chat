import { tl } from '@mtcute/core';

if (tl.LAYER !== 222) {
  console.error(`Expected mtcute TL layer 222, received ${tl.LAYER}.`);
  process.exitCode = 1;
} else {
  console.log('mtcute TL layer 222 matches the local server.');
}
