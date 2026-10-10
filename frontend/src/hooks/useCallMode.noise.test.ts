import { describe, expect, it } from 'vitest';
import { isNoiseTranscript, isSilenceReply, mentionsJarvis } from './useCallMode';

describe('isNoiseTranscript', () => {
  it.each([
    '', '  ', 'Eh.', 'Mmm...', 'Ah, oh', 'Gracias por ver el vídeo', 'Subtítulos por la comunidad de Amara.org',
    'Suscríbete al canal', '[Música]', '<noise>', '(aplausos)', 'Música.', 'a', 'Hmm hm',
  ])('treats %j as noise', (text) => {
    expect(isNoiseTranscript(text)).toBe(true);
  });

  it.each([
    'Hola', 'Sí', 'No', 'Vale', 'Abre Spotify', 'Para', 'Jarvis, abre Valorant', 'Dame un guion para el vídeo',
    '¿Qué tengo hoy en el calendario?',
  ])('keeps %j as real speech', (text) => {
    expect(isNoiseTranscript(text)).toBe(false);
  });
});

describe('isSilenceReply', () => {
  it.each(['[silencio]', 'silencio', ' (Silencio). ', '[SILENCIO]'])('detects %j', (r) => {
    expect(isSilenceReply(r)).toBe(true);
  });
  it.each(['Silencio, por favor, que me desconcentras', 'Hola', ''])('does not flag %j', (r) => {
    expect(isSilenceReply(r)).toBe(false);
  });
});
describe('mentionsJarvis', () => {
  it.each([
    'Jarvis abre Spotify', 'oye jarvis, dime algo', 'Yarvis pon música', 'harvis', 'Jarbis, qué hora es',
    'Jarvi dame un guion', 'JARVIS', 'vale Jarvis.', 'Járvis',
  ])('hears the name in %j', (text) => {
    expect(mentionsJarvis(text)).toBe(true);
  });

  it.each([
    'esto es un reel de moda', 'hola, qué tal', 'mira este vídeo del árbol', 'Marvis y su amigo', 'abre Spotify',
    'en esta parte del tutorial vamos a ver', 'no te olvides de suscribirte', 'garbanzos',
  ])('does not hear the name in %j', (text) => {
    expect(mentionsJarvis(text)).toBe(false);
  });
});