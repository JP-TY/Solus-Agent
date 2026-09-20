export function SolarSavingsChart({ requiredKwp, annualSavingsPhp, paybackYears }: {
  requiredKwp: number; annualSavingsPhp: number; paybackYears: number;
}) {
  const months = [62, 70, 66, 78, 86, 92, 88, 95, 84, 76, 68, 100];
  return (
    <div className="solus-card" data-testid="solar-savings-chart">
      <div className="solus-card-head">
        <span className="solus-chip green" aria-hidden="true" />
        <span className="kicker">Sizing result</span>
      </div>
      <h3>Your rooftop system</h3>
      <p className="solus-lede">
        A <strong>{requiredKwp} kWp array</strong> covers the sample bill, saving{" "}
        <strong className="good">PHP {annualSavingsPhp.toLocaleString()} a year</strong>{" "}
        with payback in <strong>{paybackYears} years</strong>.
      </p>
      <div className="solus-row"><span>Array size</span><span className="val">{requiredKwp} kWp</span></div>
      <div className="solus-row"><span>Blended savings / yr</span><span className="val good">PHP {annualSavingsPhp.toLocaleString()}</span></div>
      <div className="solus-row"><span>Simple payback</span><span className="val">{paybackYears} yrs</span></div>
      <div className="solus-bars" aria-hidden="true">
        {months.map((h, i) => (
          <i key={i} className={i === 11 ? "hot" : ""} style={{ height: `${h}%` }} />
        ))}
      </div>
      <div className="solus-note">Monthly yield profile, peak in the December dry season.</div>
    </div>
  );
}

export function SurveyDatePicker({ onConfirm }: { onConfirm: (date: string) => void }) {
  return (
    <div className="solus-card" data-testid="survey-date-picker">
      <div className="solus-card-head">
        <span className="solus-chip blue" aria-hidden="true" />
        <span className="kicker">Ocular visit</span>
      </div>
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
    <div className="solus-card" data-testid="tariff-card">
      <div className="solus-card-head">
        <span className="solus-chip yellow" aria-hidden="true" />
        <span className="kicker">Live tariff</span>
      </div>
      <h3>{utility}</h3>
      <p className="solus-lede">
        Generation charge <strong>PHP {ratePhp}/kWh</strong>, fetched live by the Solus browser tool.
      </p>
      <div className="solus-row"><span>Charge type</span><span className="val">Generation</span></div>
      <div className="solus-row"><span>Source</span><span className="val">DU rates page</span></div>
    </div>
  );
}
