import { describe, expect, it } from 'vitest';
import { asksQuestion, isNoiseTranscript, isSilenceReply, judgeSpeech, looksLikeEcho, mentionsJarvis } from './useCallMode';

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
describe('asksQuestion', () => {
  it.each(['¿Qué quieres escuchar?', 'Dime, ¿qué tal el día? ', '¿Seguro?"', 'Vale, ¿lo grabamos hoy?'])('is a question: %j', (r) => {
    expect(asksQuestion(r)).toBe(true);
  });
  it.each(['Hecho, crack.', 'Reproduciendo a Residente.', '¿Qué tal? Ya está.', ''])('is not a question: %j', (r) => {
    expect(asksQuestion(r)).toBe(false);
  });
});

describe('looksLikeEcho', () => {
  const last = 'Buenas, crack. Soy Jarvis. Hoy toca grabar el vídeo de Sothe Optimizer.';
  it('detects his own voice coming back', () => {
    expect(looksLikeEcho('soy Jarvis hoy toca grabar el vídeo', last)).toBe(true);
    expect(looksLikeEcho('Soy Jarvis', last)).toBe(true);
  });
  it('does not flag something new', () => {
    expect(looksLikeEcho('Jarvis, ponme Residente', last)).toBe(false);
    expect(looksLikeEcho('abre Valorant', last)).toBe(false);
  });
  it('never flags when there was no previous reply', () => {
    expect(looksLikeEcho('Jarvis', '')).toBe(false);
  });
});

describe('judgeSpeech (the rule that stops reels and friends)', () => {
  const base = { now: 100000, engagedUntil: 0, lastReply: '', requireName: true };

  it('ignores a whole reel or a chat with a friend, utterance after utterance', () => {
    const reel = [
      'en esta parte del tutorial vamos a ver cómo se hace',
      'no te olvides de darle like y suscribirte al canal',
      'tío es que me dijo que no iba a venir hoy',
      'jajaja qué fuerte, y entonces qué hiciste',
    ];
    for (const line of reel) expect(judgeSpeech(line, base)).toBe('not-addressed');
  });

  it('accepts anything that says the name', () => {
    expect(judgeSpeech('Jarvis, ponme Residente', base)).toBe('accept');
    expect(judgeSpeech('oye yarvis qué hora es', base)).toBe('accept');
  });

  it('accepts speech inside an open window, rejects it after it closes', () => {
    expect(judgeSpeech('sí, ponla', { ...base, engagedUntil: base.now + 5000 })).toBe('accept');
    expect(judgeSpeech('sí, ponla', { ...base, engagedUntil: base.now - 1 })).toBe('not-addressed');
  });

  it('treats his own words coming back as an echo, even if they contain the name', () => {
    const lastReply = 'Buenas, crack. Soy Jarvis. Hoy toca grabar el vídeo.';
    expect(judgeSpeech('Soy Jarvis, hoy toca grabar', { ...base, lastReply })).toBe('echo');
  });

  it('lets everything through when the name requirement is switched off', () => {
    expect(judgeSpeech('tío es que me dijo que no venía', { ...base, requireName: false })).toBe('accept');
  });
});