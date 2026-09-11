import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, download, setToken } from "./api";
import { groups, Field } from "./fields";
import "./style.css";

type Values = Record<string, any>;
type Report = {
  id: string;
  status: string;
  revision: number;
  updated_at: string;
  data: Record<string, Values>;
};

function Fields({
  fields,
  values,
  onChange,
  disabled = false,
}: {
  fields: Field[];
  values: Values;
  onChange: (key: string, value: any) => void;
  disabled?: boolean;
}) {
  return (
    <div className="fields">
      {fields.map((f) => (
        <label key={f.key} className={f.type === "textarea" ? "wide" : ""}>
          {f.label}
          {f.type === "textarea" ? (
            <textarea
              disabled={disabled}
              rows={3}
              maxLength={12000}
              value={values[f.key] ?? ""}
              onChange={(e) => onChange(f.key, e.target.value)}
            />
          ) : f.type === "select" ? (
            <select
              disabled={disabled}
              value={values[f.key] ?? ""}
              onChange={(e) =>
                onChange(
                  f.key,
                  f.key === "rounding_increment"
                    ? Number(e.target.value)
                    : e.target.value,
                )
              }
            >
              {f.options?.map((x) => (
                <option key={x} value={x}>
                  {x.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          ) : (
            <input
              disabled={disabled}
              type={
                ["integer", "coordinate", "decimal", "optional-money"].includes(
                  f.type || "",
                )
                  ? "number"
                  : f.type || "text"
              }
              step={f.type === "integer" ? "1" : "any"}
              value={values[f.key] ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                onChange(
                  f.key,
                  ["coordinate", "integer"].includes(f.type || "")
                    ? v === ""
                      ? null
                      : Number(v)
                    : ["optional-money", "date"].includes(f.type || "") &&
                        v === ""
                      ? null
                      : v,
                );
              }}
            />
          )}
        </label>
      ))}
    </div>
  );
}

function App() {
  const [logged, setLogged] = useState(false),
    [register, setRegister] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [config, setConfig] = useState<Values>({}),
    [reports, setReports] = useState<Report[]>([]),
    [report, setReport] = useState<Report | null>(null),
    [banks, setBanks] = useState<Values[]>([]);
  const [tab, setTab] = useState("assignment"),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  const [photoRole, setPhotoRole] = useState("interior");
  const [calc, setCalc] = useState<Values | null>(null),
    [photos, setPhotos] = useState<Values[]>([]),
    [history, setHistory] = useState<Values[]>([]),
    [mapUrl, setMapUrl] = useState(""),
    [pdfUrl, setPdfUrl] = useState("");
  const [profile, setProfile] = useState<Values | null>(null),
    [caption, setCaption] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [search, setSearch] = useState("");
  const [pathText, setPathText] = useState("");
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    api("/config")
      .then(setConfig)
      .catch(() =>
        setError("Cannot reach the backend. Check that it is running."),
      );
  }, []);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(
    () => () => {
      if (mapUrl) URL.revokeObjectURL(mapUrl);
    },
    [mapUrl],
  );
  useEffect(
    () => () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    },
    [pdfUrl],
  );
  const refresh = async () => {
    const [r, b] = await Promise.all([api("/reports"), api("/banks")]);
    setReports(r);
    setBanks(b);
  };
  const mayLeave = () => !dirty || window.confirm("Discard unsaved changes?");
  const open = async (r: Report) => {
    setReport(r);
    setDirty(false);
    setCalc(null);
    setMapUrl("");
    setPdfUrl("");
    setTab("assignment");
    setProfile(null);
    setPathText(
      r.data.property.access_path.map((p: number[]) => p.join(", ")).join("\n"),
    );
    const [p, h] = await Promise.all([
      api(`/reports/${r.id}/photos`),
      api(`/reports/${r.id}/history`),
    ]);
    setPhotos(p);
    setHistory(h);
  };
  const change = (group: string, key: string, value: any) => {
    if (!report) return;
    setReport({
      ...report,
      data: {
        ...report.data,
        [group]: { ...report.data[group], [key]: value },
      },
    });
    setDirty(true);
    setCalc(null);
    setPdfUrl("");
    if (group === "property") setMapUrl("");
  };
  const save = async () => {
    if (!report) throw Error("No report open.");
    if (!dirty) return report;
    const r = await api(`/reports/${report.id}`, "PUT", {
      revision: report.revision,
      data: report.data,
    });
    setReport(r);
    setDirty(false);
    return r as Report;
  };
  const calculate = async () => {
    const r = await save();
    setCalc(await api(`/reports/${r.id}/calculate`, "POST"));
  };
  const exportReport = async (kind: string, preview = false) => {
    const r = await save();
    const blob = await api(`/reports/${r.id}/export/${kind}`);
    if (preview) setPdfUrl(URL.createObjectURL(blob));
    else download(blob, `valuation-${r.id.slice(0, 8)}-${r.status}.${kind}`);
  };
  const locked = report?.status === "final";
  const section = groups.find((g) => g.key === tab);
  const format = (n: string) =>
    Number(n).toLocaleString("en-LK", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  if (!logged)
    return (
      <main className="login">
        <div className="login-card">
          <div className="brand">V / VALUER SUPPORT</div>
          <h1>Your report workspace</h1>
          <p>Prepare, review and preserve property valuation reports.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                const res = await api(
                  `/auth/${register ? "register" : "login"}`,
                  "POST",
                  { email, password },
                );
                setToken(res.access_token);
                setPassword("");
                await refresh();
                setLogged(true);
              });
            }}
          >
            <label>
              Email
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                minLength={12}
                maxLength={128}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <small>Use at least 12 characters. Sessions last one hour.</small>
            {error && (
              <div role="alert" className="error">
                {error}
              </div>
            )}
            <button disabled={busy} className="primary">
              {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
            </button>
          </form>
          {config.registration && (
            <button
              className="link"
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register
                ? "Already registered? Sign in"
                : "Create a valuer account"}
            </button>
          )}
        </div>
      </main>
    );

  return (
    <div className="app">
      <header>
        <button
          className="brand"
          onClick={() => {
            if (mayLeave())
              run(async () => {
                setReport(null);
                setProfile(null);
                setDirty(false);
                await refresh();
              });
          }}
        >
          V / VALUER SUPPORT
        </button>
        <div className="header-actions">
          <span>{email}</span>
          <button
            disabled={busy}
            onClick={() => {
              if (mayLeave())
                run(async () => {
                  setProfile(await api("/profile"));
                  setReport(null);
                  setDirty(false);
                });
            }}
          >
            My profile
          </button>
          <button
            onClick={() => {
              if (mayLeave()) {
                setToken("");
                setLogged(false);
                setReport(null);
                setProfile(null);
                setDirty(false);
                setMapUrl("");
                setPdfUrl("");
                setError("");
              }
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      {(error || message) && (
        <div
          role={error ? "alert" : "status"}
          className={error ? "notice error" : "notice success"}
        >
          {error || message}
          <button
            onClick={() => {
              setError("");
              setMessage("");
            }}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      )}
      {profile ? (
        <main className="profile">
          <h1>My valuer profile</h1>
          <p>
            Used for new reports. Existing reports retain their saved details.
          </p>
          <Fields
            fields={groups.find((g) => g.key === "valuer")!.fields}
            values={profile}
            onChange={(k, v) => {
              setProfile({ ...profile, [k]: v });
              setDirty(true);
            }}
          />
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await api("/profile", "PUT", profile);
                setDirty(false);
                setMessage("Profile saved.");
              })
            }
          >
            Save profile
          </button>
        </main>
      ) : !report ? (
        <main className="dashboard">
          <div className="title-row">
            <div>
              <p className="eyebrow">REPORT REGISTER</p>
              <h1>Valuation reports</h1>
              <p>
                Start a fresh property report or continue a saved assignment.
              </p>
            </div>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                run(async () => open(await api("/reports", "POST")))
              }
            >
              + New property report
            </button>
          </div>
          <input
            className="search"
            aria-label="Search reports"
            placeholder="Search reference, owner or property…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="report-list">
            {reports
              .filter((r) =>
                [
                  r.data.assignment.reference,
                  r.data.assignment.owner,
                  r.data.property.address,
                ]
                  .join(" ")
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .map((r) => (
                <button
                  className="report-row"
                  key={r.id}
                  onClick={() =>
                    run(async () => open(await api(`/reports/${r.id}`)))
                  }
                >
                  <div>
                    <strong>
                      {r.data.assignment.reference || "Untitled assignment"}
                    </strong>
                    <p>
                      {r.data.property.address ||
                        "Property details not entered"}
                    </p>
                    <small>
                      {r.data.assignment.owner || "Owner not entered"}
                    </small>
                  </div>
                  <div>
                    <span className={"badge " + r.status}>{r.status}</span>
                    <p className="muted">
                      {new Date(r.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                </button>
              ))}
            {reports.length === 0 && (
              <div className="empty">
                No reports yet. Save your valuer profile, then create your first
                property report.
              </div>
            )}
          </div>
        </main>
      ) : (
        <>
          <div className="report-heading">
            <div>
              <span className={"badge " + report.status}>{report.status}</span>
              <h1>{report.data.assignment.reference || "New assignment"}</h1>
              <p>
                {report.data.property.address ||
                  "Enter the property details below."}
              </p>
            </div>
            <div className="actions">
              <span className="muted">
                {dirty
                  ? "Unsaved changes"
                  : `Saved · revision ${report.revision}`}
              </span>
              <button
                disabled={busy || locked}
                className="primary"
                onClick={() =>
                  run(async () => {
                    await save();
                    setMessage("Draft saved.");
                  })
                }
              >
                Save draft
              </button>
            </div>
          </div>
          <div className="workspace">
            <nav aria-label="Report sections">
              {groups.map((g, i) => (
                <button
                  className={tab === g.key ? "active" : ""}
                  key={g.key}
                  onClick={() => setTab(g.key)}
                >
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  {g.title}
                </button>
              ))}
              <button
                className={tab === "photos" ? "active" : ""}
                onClick={() => setTab("photos")}
              >
                <span>08</span>Photographs
              </button>
              <button
                className={tab === "review" ? "active" : ""}
                onClick={() => setTab("review")}
              >
                <span>09</span>Review & export
              </button>
            </nav>
            <main className="editor">
              {locked && (
                <div className="info">
                  This final report is locked. Export the archived files or
                  create a revised copy for the same property.
                </div>
              )}
              {section && (
                <>
                  <h2>{section.title}</h2>
                  {tab === "bank" && (
                    <div className="bank-tools">
                      <label>
                        Load a saved bank
                        <select
                          disabled={locked}
                          defaultValue=""
                          onChange={(e) => {
                            const b = banks.find(
                              (x) => x.id === e.target.value,
                            );
                            if (b) {
                              const { id, ...data } = b;
                              setReport({
                                ...report,
                                data: { ...report.data, bank: data },
                              });
                              setDirty(true);
                            }
                          }}
                        >
                          <option value="">Select a bank profile</option>
                          {banks.map((b) => (
                            <option value={b.id} key={b.id}>
                              {b.name} — {b.branch}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        disabled={busy || locked}
                        onClick={() =>
                          run(async () => {
                            await api("/banks", "POST", report.data.bank);
                            await refresh();
                            setMessage("Bank saved for future reports.");
                          })
                        }
                      >
                        Save these bank details as a profile
                      </button>
                    </div>
                  )}
                  {tab === "building" &&
                  report.data.property.kind === "land" ? (
                    <p>
                      This is a land-only report. Building sections and floor
                      values are excluded.
                    </p>
                  ) : (
                    <Fields
                      fields={section.fields}
                      values={report.data[tab]}
                      disabled={locked || busy}
                      onChange={(k, v) => change(tab, k, v)}
                    />
                  )}
                  {tab === "property" && (
                    <section className="subsection">
                      <h3>Map snapshot</h3>
                      <p>
                        Check the point and zoom. A map does not establish
                        surveyed boundaries or show live conditions.
                      </p>
                      <label className="check">
                        <input
                          type="checkbox"
                          disabled={locked}
                          checked={report.data.property.include_map}
                          onChange={(e) =>
                            change("property", "include_map", e.target.checked)
                          }
                        />
                        Include map in exported report
                      </label>
                      {!config.maps_configured && (
                        <p className="info">
                          Maps are not configured yet. You can continue
                          preparing the report.
                        </p>
                      )}
                      {!config.map_export_allowed && (
                        <p className="info">
                          Map export is disabled. Your administrator must
                          confirm map export and retention rights before
                          enabling it.
                        </p>
                      )}
                      <button
                        disabled={busy || !config.maps_configured}
                        onClick={() =>
                          run(async () => {
                            const r = await save();
                            setMapUrl(
                              URL.createObjectURL(
                                await api(`/reports/${r.id}/map`),
                              ),
                            );
                          })
                        }
                      >
                        Save & preview map
                      </button>
                      {mapUrl && (
                        <img
                          className="map"
                          src={mapUrl}
                          alt="Map of the supplied coordinates, including original attribution"
                        />
                      )}
                      <details>
                        <summary>
                          Optional access route supplied by the valuer
                        </summary>
                        <p>
                          Enter one latitude, longitude pair per line. These
                          points draw an access path; they do not calculate
                          driving directions.
                        </p>
                        <textarea
                          disabled={locked}
                          rows={5}
                          value={pathText}
                          onChange={(e) => setPathText(e.target.value)}
                        />
                        <button
                          disabled={locked}
                          onClick={() =>
                            run(async () => {
                              const points = pathText.trim()
                                ? pathText
                                    .trim()
                                    .split("\n")
                                    .map((line) => line.split(",").map(Number))
                                : [];
                              if (
                                points.some(
                                  (p) =>
                                    p.length !== 2 ||
                                    p.some((n) => !Number.isFinite(n)),
                                )
                              )
                                throw Error(
                                  "Use one latitude, longitude pair per line.",
                                );
                              change("property", "access_path", points);
                              setMessage(
                                "Path applied. Save the report to keep it.",
                              );
                            })
                          }
                        >
                          Apply access path
                        </button>
                      </details>
                    </section>
                  )}
                  {tab === "building" &&
                    report.data.property.kind === "land_building" && (
                      <section className="subsection">
                        <h3>Floor areas and adopted rates</h3>
                        {report.data.building.floors.map(
                          (floor: Values, i: number) => (
                            <div className="floor" key={i}>
                              <Fields
                                disabled={locked}
                                fields={[
                                  { key: "name", label: "Floor name" },
                                  {
                                    key: "area_sqft",
                                    label: "Area (sq ft)",
                                    type: "decimal",
                                  },
                                  {
                                    key: "rate_per_sqft",
                                    label: "Rate (LKR / sq ft)",
                                    type: "decimal",
                                  },
                                ]}
                                values={floor}
                                onChange={(k, v) =>
                                  change(
                                    "building",
                                    "floors",
                                    report.data.building.floors.map(
                                      (x: Values, j: number) =>
                                        i === j ? { ...x, [k]: v } : x,
                                    ),
                                  )
                                }
                              />
                              <button
                                disabled={locked}
                                onClick={() =>
                                  change(
                                    "building",
                                    "floors",
                                    report.data.building.floors.filter(
                                      (_: unknown, j: number) => i !== j,
                                    ),
                                  )
                                }
                              >
                                Remove floor
                              </button>
                            </div>
                          ),
                        )}
                        <button
                          disabled={locked}
                          onClick={() =>
                            change("building", "floors", [
                              ...report.data.building.floors,
                              { name: "", area_sqft: "0", rate_per_sqft: "0" },
                            ])
                          }
                        >
                          + Add floor
                        </button>
                      </section>
                    )}
                  {tab === "valuation" && (
                    <div className="info">
                      Calculations use the land-plus-building approach shown in
                      the reference structure. Explain adopted rates and avoid
                      counting site improvements twice. Forced-sale and
                      insurance values are entered and justified by the valuer.
                    </div>
                  )}
                </>
              )}
              {tab === "photos" && (
                <>
                  <h2>Inspection photographs</h2>
                  <p>
                    Upload your inspection photographs as JPEG or PNG, up to 10
                    MB each. Choose its place in the report and add a caption.
                    Upload one cover image, one access-road image and the
                    interior photographs. Existing untagged images appear as
                    inspection photographs; remove and re-upload them to assign
                    a different place.
                  </p>
                  <div className="upload">
                    <label>
                      Photograph
                      <input
                        disabled={locked}
                        type="file"
                        accept="image/jpeg,image/png"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                      />
                    </label>
                    <label>
                      Report placement
                      <select
                        disabled={locked}
                        value={photoRole}
                        onChange={(e) => setPhotoRole(e.target.value)}
                      >
                        <option value="cover">Cover photograph</option>
                        <option value="access">Access road photograph</option>
                        <option value="interior">
                          Building / inspection photograph
                        </option>
                      </select>
                    </label>
                    <label>
                      Caption
                      <input
                        disabled={locked}
                        value={caption}
                        maxLength={280}
                        onChange={(e) => setCaption(e.target.value)}
                      />
                    </label>
                    <button
                      disabled={busy || locked || !file}
                      onClick={() =>
                        run(async () => {
                          const r = await save();
                          const form = new FormData();
                          form.append("revision", String(r.revision));
                          form.append("caption", `[${photoRole}] ${caption}`);
                          form.append("file", file!);
                          const updated = await api(
                            `/reports/${r.id}/photos`,
                            "POST",
                            form,
                          );
                          setReport(updated);
                          setPhotos(await api(`/reports/${r.id}/photos`));
                          setCaption("");
                          setFile(null);
                          setMessage("Photograph uploaded.");
                        })
                      }
                    >
                      Upload photograph
                    </button>
                  </div>
                  {photos.map((p) => (
                    <div className="photo-row" key={p.id}>
                      <span>{p.caption || "Uncaptioned photograph"}</span>
                      <div>
                        <button
                          onClick={() =>
                            run(async () =>
                              download(
                                await api(
                                  `/reports/${report.id}/photos/${p.id}`,
                                ),
                                "inspection-photo.jpg",
                              ),
                            )
                          }
                        >
                          Download
                        </button>
                        <button
                          disabled={busy || locked}
                          onClick={() =>
                            run(async () => {
                              const r = await save();
                              setReport(
                                await api(
                                  `/reports/${r.id}/photos/${p.id}?revision=${r.revision}`,
                                  "DELETE",
                                ),
                              );
                              setPhotos(await api(`/reports/${r.id}/photos`));
                            })
                          }
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </>
              )}
              {tab === "review" && (
                <>
                  <h2>Review & export</h2>
                  <p>
                    Review the source evidence, calculations, map position and
                    generated document before approving.
                  </p>
                  <div className="actions">
                    <button disabled={busy} onClick={() => run(calculate)}>
                      Save & check report
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => run(() => exportReport("docx"))}
                    >
                      Download Word
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => run(() => exportReport("pdf", true))}
                    >
                      Preview PDF
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => run(() => exportReport("pdf"))}
                    >
                      Download PDF
                    </button>
                  </div>
                  {calc && (
                    <>
                      <div className="totals">
                        {[
                          ["Land value", "land_value"],
                          ["Gross building value", "building_value"],
                          ["Calculated total", "calculated_total"],
                          ["Adopted market value", "market_value"],
                        ].map(([label, key]) => (
                          <div key={key}>
                            <span>{label}</span>
                            <strong>LKR {format(calc.calculation[key])}</strong>
                          </div>
                        ))}
                      </div>
                      <p>{calc.calculation.market_value_words}</p>
                      {calc.issues.length ? (
                        <div className="error">
                          <strong>Complete before approval</strong>
                          <ul>
                            {calc.issues.map((x: string) => (
                              <li key={x}>{x}</li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <div className="success">
                          Required-field checks passed. Professional review is
                          still required.
                        </div>
                      )}
                    </>
                  )}
                  {pdfUrl && (
                    <iframe
                      title="Generated report preview"
                      className="pdf-preview"
                      src={pdfUrl}
                    />
                  )}
                  <div className="subsection">
                    <h3>Approval</h3>
                    <div className="actions">
                      <button
                        disabled={busy || locked}
                        onClick={() =>
                          run(async () => {
                            const r = await save();
                            setReport(
                              await api(`/reports/${r.id}/review`, "POST", {
                                revision: r.revision,
                              }),
                            );
                            setMessage(
                              "Report is ready for your review. Preview the PDF before approving.",
                            );
                          })
                        }
                      >
                        Submit for review
                      </button>
                      <button
                        className="primary"
                        disabled={busy || report.status !== "review" || dirty}
                        onClick={() => {
                          if (
                            window.confirm(
                              "I confirm that I have reviewed this report, its evidence and valuation figures. Approve and lock this version?",
                            )
                          )
                            run(async () => {
                              setReport(
                                await api(
                                  `/reports/${report.id}/finalise`,
                                  "POST",
                                  {
                                    revision: report.revision,
                                    confirmed: true,
                                  },
                                ),
                              );
                              setMessage(
                                "Final Word and PDF files archived. This version is locked.",
                              );
                            });
                        }}
                      >
                        Approve & lock
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Create a revised draft for the SAME property? It will retain this property’s details and photographs.",
                            )
                          )
                            run(async () => {
                              const r = await save();
                              await open(
                                await api(`/reports/${r.id}/copy`, "POST"),
                              );
                            });
                        }}
                      >
                        Create revised copy
                      </button>
                    </div>
                    <p className="muted">
                      Approval records your account’s action. It is not a
                      cryptographic digital signature; the template retains a
                      signature line.
                    </p>
                  </div>
                  <details
                    onToggle={(e) => {
                      if (e.currentTarget.open)
                        api(`/reports/${report.id}/history`)
                          .then(setHistory)
                          .catch((err) => setError(err.message));
                    }}
                  >
                    <summary>Version and activity history</summary>
                    {history.map((h) => (
                      <div className="history" key={h.id}>
                        <span>
                          Revision {h.revision} · {h.action} ·{" "}
                          {new Date(h.created_at).toLocaleString()}
                        </span>
                        <button
                          onClick={() =>
                            run(async () =>
                              download(
                                new Blob(
                                  [
                                    JSON.stringify(
                                      await api(
                                        `/reports/${report.id}/history/${h.id}`,
                                      ),
                                      null,
                                      2,
                                    ),
                                  ],
                                  { type: "application/json" },
                                ),
                                `report-revision-${h.revision}.json`,
                              ),
                            )
                          }
                        >
                          Download inputs
                        </button>
                      </div>
                    ))}
                  </details>
                </>
              )}
            </main>
          </div>
        </>
      )}
      {busy && (
        <div className="working" role="status">
          Working…
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
