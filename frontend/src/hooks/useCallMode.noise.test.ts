import { describe, expect, it } from 'vitest';
import {
  CALL_HISTORY_MESSAGES,
  JARVIS_CALL_PERSONA,
  trimCallHistory,
  isNameOnly,
  isNoiseTranscript,
  isSilenceReply,
  judgeSpeech,
  looksLikeEcho,
  mentionsJarvis,
  startsWithJarvis,
} from './useCallMode';

describe('trimCallHistory', () => {
  const chat = (n: number) =>
    Array.from({ length: n }, (_, i) => ({ role: i % 2 === 0 ? 'user' : 'assistant', content: `m${i}` }));

  it('keeps a short conversation untouched', () => {
    const msgs = chat(5);
    expect(trimCallHistory(msgs)).toEqual(msgs);
  });

  it('keeps only the last few messages of a long one, always ending on the newest', () => {
    const msgs = chat(41); // user, assistant, ... user (the new request)
    const out = trimCallHistory(msgs);
    expect(out.length).toBeLessThanOrEqual(CALL_HISTORY_MESSAGES);
    expect(out[out.length - 1]).toEqual(msgs[msgs.length - 1]);
  });

  it('never starts with an assistant reply', () => {
    const msgs = chat(40); // ends on an assistant message, so a plain slice would start on one
    expect(trimCallHistory(msgs)[0].role).toBe('user');
  });

  it('does not loop forever or empty the list when there is no user message', () => {
    const only = [{ role: 'assistant', content: 'hola' }];
    expect(trimCallHistory(only)).toEqual(only);
  });
});

describe('call prompt', () => {
  it('forbids claiming an action that no tool performed', () => {
    expect(JARVIS_CALL_PERSONA).toMatch(/nunca digas que has hecho algo/i);
    expect(JARVIS_CALL_PERSONA).toMatch(/herramienta/i);
  });
});

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
    // anything that sounds like it
    'Jarcis pon música', 'Travis abre Discord', 'Martis, dime la hora', 'Marvis y su amigo', 'Cervis', 'Servis sube el volumen',
    'Harvey', 'Garbis', 'Jarves',
  ])('hears the name in %j', (text) => {
    expect(mentionsJarvis(text)).toBe(true);
  });

  it.each([
    'esto es un reel de moda', 'hola, qué tal', 'mira este vídeo del árbol', 'abre Spotify',
    'en esta parte del tutorial vamos a ver', 'no te olvides de suscribirte', 'garbanzos',
    'el martes quedamos', 'las partes del informe', 'Carlos dime algo',
  ])('does not hear the name in %j', (text) => {
    expect(mentionsJarvis(text)).toBe(false);
  });
});

describe('startsWithJarvis', () => {
  it.each([
    'Jarvis, ponme Residente', 'jarvis abre Spotify', 'Oye Jarvis qué hora es', 'Eh, Jarvis, dime', 'Yarvis pon música', 'JARVIS',
  ])('starts with the name: %j', (text) => {
    expect(startsWithJarvis(text)).toBe(true);
  });

  it.each([
    'ponme Residente, Jarvis', 'tío es que le dije a Jarvis que no', 'abre Spotify por favor jarvis',
    'esto es un reel', 'a mí eso no me parece bien Jarvis', '',
  ])('the name is not at the start: %j', (text) => {
    expect(startsWithJarvis(text)).toBe(false);
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
  const base = { now: 100000, pendingNameUntil: 0, lastReply: '', requireName: true };

  it('ignores a whole reel or a chat with a friend, utterance after utterance', () => {
    const reel = [
      'en esta parte del tutorial vamos a ver cómo se hace',
      'no te olvides de darle like y suscribirte al canal',
      'tío es que me dijo que no iba a venir hoy',
      'jajaja qué fuerte, y entonces qué hiciste',
      'oye, le comenté a Jarvis lo del vídeo y le pareció bien',
    ];
    for (const line of reel) expect(judgeSpeech(line, base)).toBe('not-addressed');
  });

  it('accepts only sentences that start with the name', () => {
    expect(judgeSpeech('Jarvis, ponme Residente', base)).toBe('accept');
    expect(judgeSpeech('oye yarvis qué hora es', base)).toBe('accept');
    expect(judgeSpeech('ponme Residente, Jarvis', base)).toBe('not-addressed');
  });

  it('has no open window: without the name there is no answer, even right after a question', () => {
    expect(judgeSpeech('sí, ponla', base)).toBe('not-addressed');
    expect(judgeSpeech('vale, y ahora el siguiente', { ...base, lastReply: '¿Quieres que ponga otra?' })).toBe('not-addressed');
  });

  it('after he said only the name, the next utterance continues it, but only for a few seconds', () => {
    expect(judgeSpeech('ponme Residente', { ...base, pendingNameUntil: base.now + 3000 })).toBe('continuation');
    expect(judgeSpeech('ponme Residente', { ...base, pendingNameUntil: base.now - 1 })).toBe('not-addressed');
  });

  it('treats his own words coming back as an echo, even if they contain the name', () => {
    const lastReply = 'Buenas, crack. Soy Jarvis. Hoy toca grabar el vídeo.';
    expect(judgeSpeech('Soy Jarvis, hoy toca grabar', { ...base, lastReply })).toBe('echo');
  });

  it('lets everything through only when the name requirement is switched off', () => {
    expect(judgeSpeech('tío es que me dijo que no venía', { ...base, requireName: false })).toBe('accept');
  });
});

describe('isNameOnly', () => {
  it.each(['Jarvis', 'Jarvis.', 'oye Jarvis', 'Eh, Jarvis', 'hola Jarvis', 'vale yarvis', 'Jarvis, dime'])(
    'is only a call: %j',
    (text) => {
      expect(isNameOnly(text)).toBe(true);
    },
  );
  it.each(['Jarvis, ponme Residente', 'oye Jarvis qué hora es', 'Jarvis abre Spotify', 'hola qué tal', 'dime algo', ''])(
    'is a real request or not a call: %j',
    (text) => {
      expect(isNameOnly(text)).toBe(false);
    },
  );
});
