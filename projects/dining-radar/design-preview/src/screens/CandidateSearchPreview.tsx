import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronDown,
  Clock3,
  Compass,
  ExternalLink,
  Info,
  Layers3,
  LocateFixed,
  MapPin,
  RefreshCcw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Store,
  Users,
  Utensils,
  X,
} from 'lucide-react';
import { useMemo, useState } from 'react';

/**
 * Required API additions: None required.
 *
 * Review-only implementation selected by human escape-hatch decision.
 * It performs no network request and contains no real location, shop, provider
 * response, provider identifier, or geographic coordinate fixture.
 */

type RangePreference = 'NEARBY' | 'STANDARD' | 'WIDE';
type ConceptKind =
  | 'PROXIMITY'
  | 'CAPACITY_REFERENCE'
  | 'GENRE_VARIETY'
  | 'AMENITY_REFERENCE';

type ReviewState =
  | 'NORMAL'
  | 'AUTHENTICATION_REQUIRED'
  | 'INITIAL_LOADING'
  | 'REPROPOSING'
  | 'EMPTY'
  | 'PROVIDER_UNAVAILABLE'
  | 'CONDITIONS_INVALID'
  | 'REQUEST_REJECTED'
  | 'RATE_LIMITED';

interface ReviewPosition {
  left: number;
  top: number;
}

interface Candidate {
  candidateRef: string;
  name: string;
  genre: string;
  description: string | null;
  businessHours: string | null;
  regularHoliday: string | null;
  totalSeats: number | null;
  access: string | null;
  providerPageUrl: string;
  /** Review layout only. Production markers use Candidate.location. */
  reviewPosition: ReviewPosition;
}

interface Concept {
  conceptRef: string;
  kind: ConceptKind;
  title: string;
  eyebrow: string;
  rationale: string;
  icon: typeof Compass;
  candidates: Candidate[];
}

const rangeOptions: Array<{ key: RangePreference; label: string; note: string }> = [
  { key: 'NEARBY', label: '近く', note: '移動を軽めに' },
  { key: 'STANDARD', label: '標準', note: '選択肢と近さの両立' },
  { key: 'WIDE', label: '広め', note: '新しい候補も含める' },
];

const genreOptions = ['指定なし', '和食', '洋食', 'カフェ・軽食'];

const candidates: Record<string, Candidate> = {
  a: {
    candidateRef: 'current-a',
    name: '架空食堂 青い匙',
    genre: '和食',
    description: '季節の小鉢と温かい定食を中心にした、架空の食堂です。',
    businessHours: '11:00〜14:30',
    regularHoliday: '日曜・祝日',
    totalSeats: 38,
    access: '架空オフィス街の南側',
    providerPageUrl: 'https://example.invalid/shop-a',
    reviewPosition: { left: 24, top: 36 },
  },
  b: {
    candidateRef: 'current-b',
    name: '架空ビストロ 木曜日',
    genre: '洋食',
    description: '煮込み料理とプレートランチを扱う架空のビストロです。',
    businessHours: '11:30〜15:00',
    regularHoliday: '月曜',
    totalSeats: 24,
    access: '架空文化施設の向かい',
    providerPageUrl: 'https://example.invalid/shop-b',
    reviewPosition: { left: 62, top: 23 },
  },
  c: {
    candidateRef: 'current-c',
    name: '架空喫茶 北窓',
    genre: 'カフェ・軽食',
    description: null,
    businessHours: '10:30〜16:00',
    regularHoliday: null,
    totalSeats: 18,
    access: '架空並木通り沿い',
    providerPageUrl: 'https://example.invalid/shop-c',
    reviewPosition: { left: 45, top: 65 },
  },
  d: {
    candidateRef: 'current-d',
    name: '架空ダイニング 月灯り',
    genre: '創作料理',
    description: '野菜を使った日替わり料理を出す架空のダイニングです。',
    businessHours: null,
    regularHoliday: '水曜',
    totalSeats: 52,
    access: '架空複合ビルの1階',
    providerPageUrl: 'https://example.invalid/shop-d',
    reviewPosition: { left: 72, top: 62 },
  },
};

const initialConcepts: Concept[] = [
  {
    conceptRef: 'concept-near',
    kind: 'PROXIMITY',
    title: '移動を軽く、ゆっくり話す',
    eyebrow: '近さを優先',
    rationale: '候補集合の中から、移動負担を抑えやすい店舗を優先しています。',
    icon: LocateFixed,
    candidates: [candidates.a, candidates.b, candidates.c],
  },
  {
    conceptRef: 'concept-room',
    kind: 'CAPACITY_REFERENCE',
    title: '席数を見ながら選ぶ',
    eyebrow: 'グループ利用の参考',
    rationale: '総席数の参考値が比較しやすい候補をまとめています。空席は保証しません。',
    icon: Users,
    candidates: [candidates.d, candidates.a, candidates.b],
  },
  {
    conceptRef: 'concept-variety',
    kind: 'GENRE_VARIETY',
    title: 'いつもと違う味を試す',
    eyebrow: 'ジャンルを変える',
    rationale: '異なるジャンルを横断し、選択肢に変化をつけています。',
    icon: Sparkles,
    candidates: [candidates.b, candidates.c, candidates.d],
  },
];

const replacementConcepts: Concept[] = [
  {
    conceptRef: 'concept-amenity',
    kind: 'AMENITY_REFERENCE',
    title: '落ち着いて比較する',
    eyebrow: '設備情報を参考に',
    rationale: '取得できた設備情報を比較の入口にした候補です。利用可否は詳細ページで確認します。',
    icon: Layers3,
    candidates: [candidates.c, candidates.d, candidates.a],
  },
  initialConcepts[1]!,
  initialConcepts[2]!,
];

const reviewStates: Array<{ value: ReviewState; label: string; scenario: string }> = [
  { value: 'NORMAL', label: '通常', scenario: 'TDR-CS-01/02/04' },
  { value: 'AUTHENTICATION_REQUIRED', label: '未認証', scenario: 'TDR-CS-00 / 401' },
  { value: 'INITIAL_LOADING', label: '提案中', scenario: 'loading' },
  { value: 'REPROPOSING', label: '再提案中', scenario: 'TDR-CS-03' },
  { value: 'EMPTY', label: '候補なし', scenario: 'TDR-CS-05' },
  { value: 'PROVIDER_UNAVAILABLE', label: '取得失敗', scenario: 'TDR-CS-06 / 503' },
  { value: 'CONDITIONS_INVALID', label: '条件不正', scenario: 'TDR-CS-07 / 400' },
  { value: 'REQUEST_REJECTED', label: '要求拒否', scenario: '403' },
  { value: 'RATE_LIMITED', label: '回数制限', scenario: 'TDR-CS-08 / 429' },
];

type StatusState = Exclude<ReviewState, 'NORMAL' | 'AUTHENTICATION_REQUIRED'>;

function StatusPanel({ state }: { state: StatusState }) {
  const copy = {
    INITIAL_LOADING: {
      icon: Search,
      title: 'ランチ候補を探しています',
      body: '条件に合う店舗を集め、選び方のコンセプトを組み立てています。',
      tone: 'progress',
    },
    REPROPOSING: {
      icon: RefreshCcw,
      title: '別の切り口を考えています',
      body: '前の候補へ追加せず、新しいコンセプトの組み合わせに入れ替えます。',
      tone: 'progress',
    },
    EMPTY: {
      icon: Compass,
      title: 'この条件では候補が見つかりませんでした',
      body: '検索範囲やジャンルを変えて、もう一度提案を作れます。',
      tone: 'neutral',
    },
    PROVIDER_UNAVAILABLE: {
      icon: AlertCircle,
      title: '候補情報を取得できませんでした',
      body: '時間をおいてから、もう一度お試しください。',
      tone: 'danger',
    },
    CONDITIONS_INVALID: {
      icon: Info,
      title: '選んだ条件では提案できません',
      body: '表示されている選択肢から条件を選び直してください。',
      tone: 'warning',
    },
    REQUEST_REJECTED: {
      icon: ShieldCheck,
      title: 'この操作を受け付けられませんでした',
      body: '画面を再読み込みしてから、もう一度お試しください。',
      tone: 'danger',
    },
    RATE_LIMITED: {
      icon: Clock3,
      title: '少し間をあけてお試しください',
      body: '候補の提案が続いています。しばらく待つと、再び提案できます。',
      tone: 'warning',
    },
  }[state];
  const Icon = copy.icon;

  return (
    <section className={`status-panel status-panel--${copy.tone}`} aria-live="polite">
      <div className="status-panel__icon">
        <Icon size={24} />
      </div>
      <div>
        <p className="eyebrow">現在の状態</p>
        <h2>{copy.title}</h2>
        <p>{copy.body}</p>
        {state === 'RATE_LIMITED' && <span className="retry-chip">再試行の目安: 30秒後</span>}
      </div>
      {(state === 'INITIAL_LOADING' || state === 'REPROPOSING') && (
        <div className="orbit-loader" aria-hidden="true" />
      )}
    </section>
  );
}

function SyntheticMap({
  candidates: visibleCandidates,
  activeCandidateRef,
  onActivate,
}: {
  candidates: Candidate[];
  activeCandidateRef: string | null;
  onActivate: (candidateRef: string) => void;
}) {
  return (
    <section className="map-panel" aria-label="候補店舗の合成位置図">
      <div className="map-panel__topbar">
        <div>
          <p className="eyebrow">候補の位置関係</p>
          <h3>お店を地図で見比べる</h3>
        </div>
        <span className="map-note"><MapPin size={14} />検索基点は表示しません</span>
      </div>
      <div className="synthetic-map">
        <div className="map-grid" aria-hidden="true" />
        <div className="map-block map-block--one" aria-hidden="true" />
        <div className="map-block map-block--two" aria-hidden="true" />
        <div className="map-block map-block--three" aria-hidden="true" />
        <div className="map-road map-road--one" aria-hidden="true" />
        <div className="map-road map-road--two" aria-hidden="true" />
        {visibleCandidates.map((candidate, index) => {
          const isActive = candidate.candidateRef === activeCandidateRef;
          return (
            <button
              className={`map-marker${isActive ? ' map-marker--active' : ''}`}
              key={candidate.candidateRef}
              style={{ left: `${candidate.reviewPosition.left}%`, top: `${candidate.reviewPosition.top}%` }}
              onClick={() => onActivate(candidate.candidateRef)}
              aria-label={`${candidate.name}のカードを強調`}
            >
              <span><b>{index + 1}</b></span>
              <small>{candidate.name}</small>
            </button>
          );
        })}
        <div className="map-legend">
          <span><Store size={14} />候補店舗</span>
          <span>合成位置図</span>
        </div>
      </div>
      <div className="map-attribution">
        本番地図: <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>
      </div>
    </section>
  );
}

function CandidateCard({
  candidate,
  index,
  active,
  onActivate,
}: {
  candidate: Candidate;
  index: number;
  active: boolean;
  onActivate: () => void;
}) {
  return (
    <article
      className={`candidate-card${active ? ' candidate-card--active' : ''}`}
      onMouseEnter={onActivate}
      onFocus={onActivate}
    >
      <button className="candidate-card__focus" onClick={onActivate} aria-label={`${candidate.name}を地図で強調`}>
        <span>{index + 1}</span>
      </button>
      <div className="candidate-card__body">
        <div className="candidate-card__heading">
          <div>
            <span className="genre-chip">{candidate.genre}</span>
            <h3>{candidate.name}</h3>
          </div>
          {active && <span className="active-chip"><MapPin size={13} />地図で選択中</span>}
        </div>
        <p className={`description${candidate.description ? '' : ' muted'}`}>
          {candidate.description ?? '紹介情報なし'}
        </p>
        <dl className="fact-grid">
          <div>
            <dt><Clock3 size={14} />営業時間</dt>
            <dd>{candidate.businessHours ?? '情報なし'}</dd>
          </div>
          <div>
            <dt><RotateCcw size={14} />定休日</dt>
            <dd>{candidate.regularHoliday ?? '情報なし'}</dd>
          </div>
          <div>
            <dt><Users size={14} />総席数</dt>
            <dd>{candidate.totalSeats === null ? '情報なし' : `${candidate.totalSeats}席`}</dd>
          </div>
          <div>
            <dt><Compass size={14} />アクセス</dt>
            <dd>{candidate.access ?? '情報なし'}</dd>
          </div>
        </dl>
        <a className="provider-link" href={candidate.providerPageUrl}>
          メニューなどを確認 <ExternalLink size={15} />
        </a>
      </div>
    </article>
  );
}

function AuthRequired() {
  return (
    <main className="auth-layout">
      <section className="auth-card">
        <div className="brand-mark"><Utensils size={24} /></div>
        <p className="eyebrow">ランチレーダー</p>
        <h1>幹事向けの候補提案</h1>
        <p>候補を見るには、招待されたアカウントでサインインしてください。</p>
        <button className="primary-button">サインインへ <ArrowRight size={17} /></button>
        <span className="privacy-note"><ShieldCheck size={15} />検索地点や候補は表示されていません</span>
      </section>
    </main>
  );
}

export default function CandidateSearchPreview() {
  const [reviewState, setReviewState] = useState<ReviewState>('NORMAL');
  const [rangePreference, setRangePreference] = useState<RangePreference>('NEARBY');
  const [genre, setGenre] = useState('指定なし');
  const [concepts, setConcepts] = useState(initialConcepts);
  const [selectedConceptRef, setSelectedConceptRef] = useState(initialConcepts[0].conceptRef);
  const [activeCandidateRef, setActiveCandidateRef] = useState<string | null>(
    initialConcepts[0].candidates[0].candidateRef,
  );
  const [reviewOpen, setReviewOpen] = useState(true);
  const [generation, setGeneration] = useState(1);

  const selectedConcept = useMemo(
    () => concepts.find((concept) => concept.conceptRef === selectedConceptRef) ?? concepts[0]!,
    [concepts, selectedConceptRef],
  );

  const selectConcept = (concept: Concept) => {
    setSelectedConceptRef(concept.conceptRef);
    setActiveCandidateRef(concept.candidates[0]?.candidateRef ?? null);
  };

  const regenerate = () => {
    setReviewState('REPROPOSING');
    window.setTimeout(() => {
      const next = generation % 2 === 1 ? replacementConcepts : initialConcepts;
      setConcepts(next);
      setSelectedConceptRef(next[0].conceptRef);
      setActiveCandidateRef(next[0].candidates[0]?.candidateRef ?? null);
      setGeneration((current) => current + 1);
      setReviewState('NORMAL');
    }, 850);
  };

  const requestProposals = () => {
    setReviewState('INITIAL_LOADING');
    window.setTimeout(() => setReviewState('NORMAL'), 850);
  };

  const setScenario = (state: ReviewState) => {
    setReviewState(state);
    if (state === 'NORMAL') {
      setConcepts(initialConcepts);
      selectConcept(initialConcepts[0]);
    }
  };

  return (
    <div className="app-shell">
      {reviewState === 'AUTHENTICATION_REQUIRED' ? (
        <AuthRequired />
      ) : (
        <>
          <header className="app-header">
            <a className="brand" href="#top" aria-label="ランチレーダーのトップ">
              <span className="brand-mark"><Utensils size={20} /></span>
              <span><strong>ランチレーダー</strong></span>
            </a>
            <div className="header-meta">
              <span><ShieldCheck size={15} />検索地点は非公開</span>
              <button className="avatar" aria-label="アカウントメニュー">幹</button>
            </div>
          </header>

          <main id="top" className="content-shell">
            <section className="hero">
              <div>
                <h1>ランチ候補を探す</h1>
                <p className="hero__lead">
                  条件を選ぶと、候補をコンセプト別に表示します。地図と店舗情報を比較して選べます。
                </p>
              </div>
            </section>

            <section className="search-panel" aria-label="候補の補助条件">
              <div className="search-panel__intro">
                <span className="step-number">1</span>
                <div><p className="eyebrow">まずは補助条件</p><h2>どの範囲から探しますか？</h2></div>
              </div>
              <div className="range-control" role="group" aria-label="検索範囲の希望">
                {rangeOptions.map((option) => (
                  <button
                    key={option.key}
                    className={rangePreference === option.key ? 'selected' : ''}
                    onClick={() => setRangePreference(option.key)}
                  >
                    <span>{rangePreference === option.key && <Check size={14} />}{option.label}</span>
                    <small>{option.note}</small>
                  </button>
                ))}
              </div>
              <label className="select-control">
                <span>ジャンル</span>
                <select value={genre} onChange={(event) => setGenre(event.target.value)}>
                  {genreOptions.map((option) => <option key={option}>{option}</option>)}
                </select>
                <ChevronDown size={16} aria-hidden="true" />
              </label>
              <div className="lunch-required"><Utensils size={16} /><span>ランチ営業</span><strong>必須</strong></div>
              <button className="primary-button search-button" onClick={requestProposals}>
                <Search size={17} />候補を提案
              </button>
            </section>

            {reviewState !== 'NORMAL' ? (
              <StatusPanel state={reviewState} />
            ) : (
              <>
                <section className="proposal-section">
                  <div className="section-heading">
                    <div className="section-heading__title">
                      <span className="step-number">2</span>
                      <div><p className="eyebrow">コンセプト</p><h2>候補の見方を選ぶ</h2></div>
                    </div>
                    <div className="proposal-meta"><Sparkles size={15} />第{generation}案</div>
                  </div>
                  <div className="concept-grid">
                    {concepts.map((concept) => {
                      const selected = concept.conceptRef === selectedConcept.conceptRef;
                      const Icon = concept.icon;
                      return (
                        <button
                          key={concept.conceptRef}
                          className={`concept-card${selected ? ' concept-card--selected' : ''}`}
                          onClick={() => selectConcept(concept)}
                        >
                          <span className="concept-card__icon"><Icon size={21} /></span>
                          <span className="concept-card__eyebrow">{concept.eyebrow}</span>
                          <strong>{concept.title}</strong>
                          <p>{concept.rationale}</p>
                          <span className="concept-card__action">この切り口で見る <ArrowRight size={15} /></span>
                        </button>
                      );
                    })}
                  </div>
                </section>

                <section className="comparison-section">
                  <div className="comparison-heading">
                    <div>
                      <p className="eyebrow">選択中のコンセプト</p>
                      <h2>{selectedConcept.title}</h2>
                      <p>{selectedConcept.rationale}</p>
                    </div>
                    <button className="secondary-button" onClick={regenerate}>
                      <RefreshCcw size={16} />別の切り口で再提案
                    </button>
                  </div>
                  <div className="comparison-grid">
                    <SyntheticMap
                      candidates={selectedConcept.candidates}
                      activeCandidateRef={activeCandidateRef}
                      onActivate={setActiveCandidateRef}
                    />
                    <section className="candidate-list" aria-label="候補店舗一覧">
                      <div className="candidate-list__header">
                        <div><p className="eyebrow">候補店舗</p><h3>{selectedConcept.candidates.length}件を比較</h3></div>
                        <span>席数は参考情報です</span>
                      </div>
                      <div className="candidate-list__scroll">
                        {selectedConcept.candidates.map((candidate, index) => (
                          <CandidateCard
                            key={candidate.candidateRef}
                            candidate={candidate}
                            index={index}
                            active={candidate.candidateRef === activeCandidateRef}
                            onActivate={() => setActiveCandidateRef(candidate.candidateRef)}
                          />
                        ))}
                      </div>
                    </section>
                  </div>
                </section>
              </>
            )}
          </main>

          <footer className="app-footer">
            <div><strong>ランチレーダー</strong><span>表示情報は参考です。営業状況・予約可否は店舗ページでご確認ください。</span></div>
            <a href="http://webservice.recruit.co.jp/">Powered by ホットペッパーグルメ Webサービス</a>
          </footer>
        </>
      )}

      <aside className={`review-console${reviewOpen ? ' review-console--open' : ''}`}>
        <button className="review-console__toggle" onClick={() => setReviewOpen((open) => !open)}>
          {reviewOpen ? <X size={16} /> : <Layers3 size={16} />}
          <span>{reviewOpen ? '閉じる' : 'レビュー状態'}</span>
        </button>
        {reviewOpen && (
          <div className="review-console__body">
            <div><span>REVIEW ONLY</span><strong>状態プレビュー</strong><small>本番画面には含まれません</small></div>
            <div className="review-state-grid">
              {reviewStates.map((state) => (
                <button
                  key={state.value}
                  className={reviewState === state.value ? 'active' : ''}
                  onClick={() => setScenario(state.value)}
                >
                  <span>{state.label}</span><small>{state.scenario}</small>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
