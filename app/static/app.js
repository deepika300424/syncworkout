const query = document.querySelector('#query');
const searchButton = document.querySelector('#search-button');
const micButton = document.querySelector('#mic-button');
const micStatus = document.querySelector('#mic-status');
const speakToggle = document.querySelector('#speak-toggle');
const loading = document.querySelector('#loading');
const answerPanel = document.querySelector('#answer-panel');
const answer = document.querySelector('#answer');
const results = document.querySelector('#results');
const error = document.querySelector('#error');

function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

function mediaUrl(path) {
  if (!path) return '';
  return `/media/${path.replaceAll('\\', '/')}`;
}

function renderInlineMarkdown(text) {
  const fragment = document.createDocumentFragment();
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((part) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const strong = document.createElement('strong');
      strong.textContent = part.slice(2, -2);
      fragment.append(strong);
    } else {
      fragment.append(document.createTextNode(part));
    }
  });
  return fragment;
}

function renderAnswer(text) {
  answer.replaceChildren();
  const lines = String(text || '').split(/\r?\n/);
  let list;
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      list = null;
      return;
    }
    if (trimmed.startsWith('* ')) {
      if (!list) {
        list = document.createElement('ul');
        answer.append(list);
      }
      const item = document.createElement('li');
      item.append(renderInlineMarkdown(trimmed.slice(2)));
      list.append(item);
      return;
    }
    const paragraph = document.createElement('p');
    paragraph.append(renderInlineMarkdown(trimmed));
    answer.append(paragraph);
    list = null;
  });
  answerPanel.hidden = false;
  if (speakToggle.checked && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(String(text || '')));
  }
}

function renderResults(payload) {
  results.replaceChildren();
  const workouts = payload?.workouts || [];
  const exercises = payload?.exercises || [];
  const sections = payload?.sections || [];
  const groupedExercises = new Map();
  exercises.forEach((exercise) => {
    const key = exercise.workout_id || 'recommended';
    if (!groupedExercises.has(key)) groupedExercises.set(key, []);
    groupedExercises.get(key).push(exercise);
  });
  const workoutItems = [...workouts];
  [...exercises, ...sections].forEach((item) => {
    const workoutId = item.workout_id || 'recommended';
    if (!workoutItems.some((workout) => workout.workout_id === workoutId)) {
      workoutItems.push({ workout_id: workoutId, workout_title: item.workout_title || 'Recommended workout' });
    }
  });
  if (!workoutItems.length) workoutItems.push({ workout_id: 'recommended', workout_title: 'Recommended workout' });
  workoutItems.forEach((workout) => {
    const section = document.createElement('section');
    section.className = 'workout-group';
    const introUrl = workout.intro_url || mediaUrl(workout.local_intro);
    section.innerHTML = `<div class="workout-heading"><div><p class="eyebrow">WORKOUT</p><h2></h2></div>${introUrl ? `<button class="secondary-button" data-play="${introUrl}">&#9654; Play workout</button>` : ''}</div><div class="workout-detail"></div><div class="exercise-grid"></div>`;
    section.querySelector('.workout-heading h2').textContent = workout.workout_title || 'Recommended workout';
    const matchingSections = sections.filter((item) => item.workout_id === workout.workout_id);
    section.querySelector('.workout-detail').textContent = matchingSections.map((item) => item.section_title).filter(Boolean).join(' · ');
    const grid = section.querySelector('.exercise-grid');
    (groupedExercises.get(workout.workout_id) || []).forEach((exercise) => {
      const videoUrl = exercise.video_url || mediaUrl(exercise.local_video);
      const previewUrl = exercise.preview_url || mediaUrl(exercise.local_preview || exercise.local_image);
      const audioUrl = (exercise.audio_urls || [])[0] || mediaUrl((exercise.local_audio_cues || [])[0]);
      const card = document.createElement('article');
      card.className = 'card';
      card.innerHTML = `
        ${videoUrl ? `<video controls preload="metadata" ${previewUrl ? `poster="${previewUrl}"` : ''} src="${videoUrl}"></video>` : ''}
        <div class="card-body"><h3></h3><p class="meta"></p><div class="actions">
        ${audioUrl ? `<button class="audio-button" data-play="${audioUrl}">&#9835; Play cue</button>` : ''}
        ${videoUrl ? `<a class="watch" target="_blank" rel="noreferrer" href="${videoUrl}">Open video &#8599;</a>` : '<span class="meta">No video available</span>'}
        </div></div>`;
      card.querySelector('h3').textContent = exercise.exercise_title || 'Recommended exercise';
      card.querySelector('.meta').textContent = [exercise.section_title].filter(Boolean).join(' / ');
      grid.append(card);
    });
    if (!grid.children.length) grid.remove();
    results.append(section);
  });
  results.querySelectorAll('[data-play]').forEach((button) => {
    button.addEventListener('click', () => playMedia(button.dataset.play, button));
  });
}

let backgroundAudio;
function playMedia(url, button) {
  if (!backgroundAudio) backgroundAudio = new Audio();
  backgroundAudio.pause();
  backgroundAudio.src = url;
  backgroundAudio.play().then(() => {
    document.querySelectorAll('[data-play]').forEach((item) => { item.classList.remove('playing'); });
    button.classList.add('playing');
  }).catch(() => showError('The browser blocked playback. Click the play control again.'));
}

async function ask() {
  const text = query.value.trim();
  if (!text) return;
  loading.hidden = false;
  error.hidden = true;
  searchButton.disabled = true;
  try {
    const response = await fetch('/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: text }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'The workout search failed.');
    renderAnswer(data.answer);
    renderResults(data.render_payload);
  } catch (requestError) {
    showError(requestError.message);
  } finally {
    loading.hidden = true;
    searchButton.disabled = false;
  }
}

searchButton.addEventListener('click', ask);
query.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); ask(); } });

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.onstart = () => { micButton.classList.add('listening'); micStatus.textContent = 'Listening...'; };
  recognition.onend = () => { micButton.classList.remove('listening'); micStatus.textContent = 'Type or use the microphone'; };
  recognition.onerror = () => { micButton.classList.remove('listening'); micStatus.textContent = 'Microphone unavailable'; };
  recognition.onresult = (event) => { query.value = event.results[0][0].transcript; ask(); };
  micButton.addEventListener('click', () => recognition.start());
} else {
  micButton.disabled = true;
  micStatus.textContent = 'Voice input is not supported in this browser';
}
