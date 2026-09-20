export function SolarSavingsChart({ requiredKwp, annualSavingsPhp, paybackYears }: {
  requiredKwp: number; annualSavingsPhp: number; paybackYears: number;
}) {
  const months = [62, 70, 66, 78, 86, 92, 88, 95, 84, 76, 68, 100];
  return (
    <div className="solus-card green" data-testid="solar-savings-chart">
      <div className="kicker">Sizing result</div>
      <h3>Your rooftop system</h3>
      <div className="solus-stat">{requiredKwp} <small>kWp</small></div>
      <div className="solus-row"><span>Blended savings / yr</span><span className="val good">PHP {annualSavingsPhp.toLocaleString()}</span></div>
      <div className="solus-row"><span>Simple payback</span><span className="val">{paybackYears} yrs</span></div>
      <div className="solus-bars" aria-hidden="true">
        {months.map((h, i) => (
          <i key={i} className={i === 11 ? "hot" : ""} style={{ height: `${h}%` }} />
        ))}
      </div>
      <div className="solus-note">Monthly yield profile · peak in December dry season.</div>
    </div>
  );
}

export function SurveyDatePicker({ onConfirm }: { onConfirm: (date: string) => void }) {
  return (
    <div className="solus-card" data-testid="survey-date-picker">
      <div className="kicker">Ocular visit</div>
      <h3>Confirm survey date</h3>
      <input type="date" aria-label="Survey date" id="solus-survey-date" />
      <button onClick={() => {
        const el = document.getElementById("solus-survey-date") as HTMLInputElement;
        onConfirm(el?.value ?? "");
      }}>Confirm survey</button>
      <div className="solus-note">A licensed installer confirms roof fit and shading on site.</div>
    </div>
  );
}

export function TariffCard({ utility, ratePhp }: { utility: string; ratePhp: number }) {
  return (
    <div className="solus-card yellow" data-testid="tariff-card">
      <div className="kicker">Live tariff</div>
      <h3>{utility}</h3>
      <div className="solus-stat">₱{ratePhp} <small>/ kWh</small></div>
      <div className="solus-row"><span>Source</span><span className="val">Generation charge</span></div>
      <div className="solus-note">Fetched live by the Solus browser tool from the DU rates page.</div>
    </div>
  );
}
