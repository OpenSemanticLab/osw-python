/**
* @vue/shared v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function bs(e) {
  const t = /* @__PURE__ */ Object.create(null);
  for (const s of e.split(",")) t[s] = 1;
  return (s) => s in t;
}
const V = {}, Ye = [], xe = () => {
}, Tr = () => !1, Lt = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), xs = (e) => e.startsWith("onUpdate:"), te = Object.assign, ys = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, Cr = Object.prototype.hasOwnProperty, D = (e, t) => Cr.call(e, t), P = Array.isArray, ze = (e) => Ut(e) === "[object Map]", mn = (e) => Ut(e) === "[object Set]", R = (e) => typeof e == "function", G = (e) => typeof e == "string", Fe = (e) => typeof e == "symbol", q = (e) => e !== null && typeof e == "object", bn = (e) => (q(e) || R(e)) && R(e.then) && R(e.catch), xn = Object.prototype.toString, Ut = (e) => xn.call(e), Er = (e) => Ut(e).slice(8, -1), yn = (e) => Ut(e) === "[object Object]", vs = (e) => G(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, lt = /* @__PURE__ */ bs(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), Vt = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, Or = /-(\w)/g, Me = Vt(
  (e) => e.replace(Or, (t, s) => s ? s.toUpperCase() : "")
), Ar = /\B([A-Z])/g, qe = Vt(
  (e) => e.replace(Ar, "-$1").toLowerCase()
), vn = Vt((e) => e.charAt(0).toUpperCase() + e.slice(1)), zt = Vt(
  (e) => e ? `on${vn(e)}` : ""
), Be = (e, t) => !Object.is(e, t), Xt = (e, ...t) => {
  for (let s = 0; s < e.length; s++)
    e[s](...t);
}, wn = (e, t, s, n = !1) => {
  Object.defineProperty(e, t, {
    configurable: !0,
    enumerable: !1,
    writable: n,
    value: s
  });
}, Pr = (e) => {
  const t = parseFloat(e);
  return isNaN(t) ? e : t;
};
let Ks;
const Bt = () => Ks || (Ks = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function ws(e) {
  if (P(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = G(n) ? Fr(n) : ws(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (G(e) || q(e))
    return e;
}
const Rr = /;(?![^(]*\))/g, Ir = /:([^]+)/, Mr = /\/\*[^]*?\*\//g;
function Fr(e) {
  const t = {};
  return e.replace(Mr, "").split(Rr).forEach((s) => {
    if (s) {
      const n = s.split(Ir);
      n.length > 1 && (t[n[0].trim()] = n[1].trim());
    }
  }), t;
}
function Ss(e) {
  let t = "";
  if (G(e))
    t = e;
  else if (P(e))
    for (let s = 0; s < e.length; s++) {
      const n = Ss(e[s]);
      n && (t += n + " ");
    }
  else if (q(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const Dr = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", jr = /* @__PURE__ */ bs(Dr);
function Sn(e) {
  return !!e || e === "";
}
const Tn = (e) => !!(e && e.__v_isRef === !0), Cn = (e) => G(e) ? e : e == null ? "" : P(e) || q(e) && (e.toString === xn || !R(e.toString)) ? Tn(e) ? Cn(e.value) : JSON.stringify(e, En, 2) : String(e), En = (e, t) => Tn(t) ? En(e, t.value) : ze(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[Zt(n, i) + " =>"] = r, s),
    {}
  )
} : mn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => Zt(s))
} : Fe(t) ? Zt(t) : q(t) && !P(t) && !yn(t) ? String(t) : t, Zt = (e, t = "") => {
  var s;
  return (
    // Symbol.description in es2019+ so we need to cast here to pass
    // the lib: es2016 check
    Fe(e) ? `Symbol(${(s = e.description) != null ? s : t})` : e
  );
};
/**
* @vue/reactivity v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let oe;
class Hr {
  constructor(t = !1) {
    this.detached = t, this._active = !0, this.effects = [], this.cleanups = [], this._isPaused = !1, this.parent = oe, !t && oe && (this.index = (oe.scopes || (oe.scopes = [])).push(
      this
    ) - 1);
  }
  get active() {
    return this._active;
  }
  pause() {
    if (this._active) {
      this._isPaused = !0;
      let t, s;
      if (this.scopes)
        for (t = 0, s = this.scopes.length; t < s; t++)
          this.scopes[t].pause();
      for (t = 0, s = this.effects.length; t < s; t++)
        this.effects[t].pause();
    }
  }
  /**
   * Resumes the effect scope, including all child scopes and effects.
   */
  resume() {
    if (this._active && this._isPaused) {
      this._isPaused = !1;
      let t, s;
      if (this.scopes)
        for (t = 0, s = this.scopes.length; t < s; t++)
          this.scopes[t].resume();
      for (t = 0, s = this.effects.length; t < s; t++)
        this.effects[t].resume();
    }
  }
  run(t) {
    if (this._active) {
      const s = oe;
      try {
        return oe = this, t();
      } finally {
        oe = s;
      }
    }
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  on() {
    oe = this;
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  off() {
    oe = this.parent;
  }
  stop(t) {
    if (this._active) {
      this._active = !1;
      let s, n;
      for (s = 0, n = this.effects.length; s < n; s++)
        this.effects[s].stop();
      for (this.effects.length = 0, s = 0, n = this.cleanups.length; s < n; s++)
        this.cleanups[s]();
      if (this.cleanups.length = 0, this.scopes) {
        for (s = 0, n = this.scopes.length; s < n; s++)
          this.scopes[s].stop(!0);
        this.scopes.length = 0;
      }
      if (!this.detached && this.parent && !t) {
        const r = this.parent.scopes.pop();
        r && r !== this && (this.parent.scopes[this.index] = r, r.index = this.index);
      }
      this.parent = void 0;
    }
  }
}
function $r() {
  return oe;
}
let U;
const Qt = /* @__PURE__ */ new WeakSet();
class On {
  constructor(t) {
    this.fn = t, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, oe && oe.active && oe.effects.push(this);
  }
  pause() {
    this.flags |= 64;
  }
  resume() {
    this.flags & 64 && (this.flags &= -65, Qt.has(this) && (Qt.delete(this), this.trigger()));
  }
  /**
   * @internal
   */
  notify() {
    this.flags & 2 && !(this.flags & 32) || this.flags & 8 || Pn(this);
  }
  run() {
    if (!(this.flags & 1))
      return this.fn();
    this.flags |= 2, Ws(this), Rn(this);
    const t = U, s = ce;
    U = this, ce = !0;
    try {
      return this.fn();
    } finally {
      In(this), U = t, ce = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Es(t);
      this.deps = this.depsTail = void 0, Ws(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? Qt.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
  }
  /**
   * @internal
   */
  runIfDirty() {
    ls(this) && this.run();
  }
  get dirty() {
    return ls(this);
  }
}
let An = 0, ft, ct;
function Pn(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = ct, ct = e;
    return;
  }
  e.next = ft, ft = e;
}
function Ts() {
  An++;
}
function Cs() {
  if (--An > 0)
    return;
  if (ct) {
    let t = ct;
    for (ct = void 0; t; ) {
      const s = t.next;
      t.next = void 0, t.flags &= -9, t = s;
    }
  }
  let e;
  for (; ft; ) {
    let t = ft;
    for (ft = void 0; t; ) {
      const s = t.next;
      if (t.next = void 0, t.flags &= -9, t.flags & 1)
        try {
          t.trigger();
        } catch (n) {
          e || (e = n);
        }
      t = s;
    }
  }
  if (e) throw e;
}
function Rn(e) {
  for (let t = e.deps; t; t = t.nextDep)
    t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function In(e) {
  let t, s = e.depsTail, n = s;
  for (; n; ) {
    const r = n.prevDep;
    n.version === -1 ? (n === s && (s = r), Es(n), Nr(n)) : t = n, n.dep.activeLink = n.prevActiveLink, n.prevActiveLink = void 0, n = r;
  }
  e.deps = t, e.depsTail = s;
}
function ls(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (t.dep.version !== t.version || t.dep.computed && (Mn(t.dep.computed) || t.dep.version !== t.version))
      return !0;
  return !!e._dirty;
}
function Mn(e) {
  if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === pt))
    return;
  e.globalVersion = pt;
  const t = e.dep;
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !ls(e)) {
    e.flags &= -3;
    return;
  }
  const s = U, n = ce;
  U = e, ce = !0;
  try {
    Rn(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    U = s, ce = n, In(e), e.flags &= -3;
  }
}
function Es(e, t = !1) {
  const { dep: s, prevSub: n, nextSub: r } = e;
  if (n && (n.nextSub = r, e.prevSub = void 0), r && (r.prevSub = n, e.nextSub = void 0), s.subs === e && (s.subs = n, !n && s.computed)) {
    s.computed.flags &= -5;
    for (let i = s.computed.deps; i; i = i.nextDep)
      Es(i, !0);
  }
  !t && !--s.sc && s.map && s.map.delete(s.key);
}
function Nr(e) {
  const { prevDep: t, nextDep: s } = e;
  t && (t.nextDep = s, e.prevDep = void 0), s && (s.prevDep = t, e.nextDep = void 0);
}
let ce = !0;
const Fn = [];
function De() {
  Fn.push(ce), ce = !1;
}
function je() {
  const e = Fn.pop();
  ce = e === void 0 ? !0 : e;
}
function Ws(e) {
  const { cleanup: t } = e;
  if (e.cleanup = void 0, t) {
    const s = U;
    U = void 0;
    try {
      t();
    } finally {
      U = s;
    }
  }
}
let pt = 0;
class Lr {
  constructor(t, s) {
    this.sub = t, this.dep = s, this.version = s.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
  }
}
class Dn {
  constructor(t) {
    this.computed = t, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0;
  }
  track(t) {
    if (!U || !ce || U === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== U)
      s = this.activeLink = new Lr(U, this), U.deps ? (s.prevDep = U.depsTail, U.depsTail.nextDep = s, U.depsTail = s) : U.deps = U.depsTail = s, jn(s);
    else if (s.version === -1 && (s.version = this.version, s.nextDep)) {
      const n = s.nextDep;
      n.prevDep = s.prevDep, s.prevDep && (s.prevDep.nextDep = n), s.prevDep = U.depsTail, s.nextDep = void 0, U.depsTail.nextDep = s, U.depsTail = s, U.deps === s && (U.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, pt++, this.notify(t);
  }
  notify(t) {
    Ts();
    try {
      for (let s = this.subs; s; s = s.prevSub)
        s.sub.notify() && s.sub.dep.notify();
    } finally {
      Cs();
    }
  }
}
function jn(e) {
  if (e.dep.sc++, e.sub.flags & 4) {
    const t = e.dep.computed;
    if (t && !e.dep.subs) {
      t.flags |= 20;
      for (let n = t.deps; n; n = n.nextDep)
        jn(n);
    }
    const s = e.dep.subs;
    s !== e && (e.prevSub = s, s && (s.nextSub = e)), e.dep.subs = e;
  }
}
const fs = /* @__PURE__ */ new WeakMap(), Ke = Symbol(
  ""
), cs = Symbol(
  ""
), gt = Symbol(
  ""
);
function z(e, t, s) {
  if (ce && U) {
    let n = fs.get(e);
    n || fs.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Dn()), r.map = n, r.key = s), r.track();
  }
}
function Ce(e, t, s, n, r, i) {
  const o = fs.get(e);
  if (!o) {
    pt++;
    return;
  }
  const f = (u) => {
    u && u.trigger();
  };
  if (Ts(), t === "clear")
    o.forEach(f);
  else {
    const u = P(e), h = u && vs(s);
    if (u && s === "length") {
      const a = Number(n);
      o.forEach((p, S) => {
        (S === "length" || S === gt || !Fe(S) && S >= a) && f(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && f(o.get(s)), h && f(o.get(gt)), t) {
        case "add":
          u ? h && f(o.get("length")) : (f(o.get(Ke)), ze(e) && f(o.get(cs)));
          break;
        case "delete":
          u || (f(o.get(Ke)), ze(e) && f(o.get(cs)));
          break;
        case "set":
          ze(e) && f(o.get(Ke));
          break;
      }
  }
  Cs();
}
function Je(e) {
  const t = H(e);
  return t === e ? t : (z(t, "iterate", gt), ye(e) ? t : t.map(le));
}
function Os(e) {
  return z(e = H(e), "iterate", gt), e;
}
const Ur = {
  __proto__: null,
  [Symbol.iterator]() {
    return kt(this, Symbol.iterator, le);
  },
  concat(...e) {
    return Je(this).concat(
      ...e.map((t) => P(t) ? Je(t) : t)
    );
  },
  entries() {
    return kt(this, "entries", (e) => (e[1] = le(e[1]), e));
  },
  every(e, t) {
    return we(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return we(this, "filter", e, t, (s) => s.map(le), arguments);
  },
  find(e, t) {
    return we(this, "find", e, t, le, arguments);
  },
  findIndex(e, t) {
    return we(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return we(this, "findLast", e, t, le, arguments);
  },
  findLastIndex(e, t) {
    return we(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return we(this, "forEach", e, t, void 0, arguments);
  },
  includes(...e) {
    return es(this, "includes", e);
  },
  indexOf(...e) {
    return es(this, "indexOf", e);
  },
  join(e) {
    return Je(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return es(this, "lastIndexOf", e);
  },
  map(e, t) {
    return we(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return rt(this, "pop");
  },
  push(...e) {
    return rt(this, "push", e);
  },
  reduce(e, ...t) {
    return qs(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return qs(this, "reduceRight", e, t);
  },
  shift() {
    return rt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return we(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return rt(this, "splice", e);
  },
  toReversed() {
    return Je(this).toReversed();
  },
  toSorted(e) {
    return Je(this).toSorted(e);
  },
  toSpliced(...e) {
    return Je(this).toSpliced(...e);
  },
  unshift(...e) {
    return rt(this, "unshift", e);
  },
  values() {
    return kt(this, "values", le);
  }
};
function kt(e, t, s) {
  const n = Os(e), r = n[t]();
  return n !== e && !ye(e) && (r._next = r.next, r.next = () => {
    const i = r._next();
    return i.value && (i.value = s(i.value)), i;
  }), r;
}
const Vr = Array.prototype;
function we(e, t, s, n, r, i) {
  const o = Os(e), f = o !== e && !ye(e), u = o[t];
  if (u !== Vr[t]) {
    const p = u.apply(e, i);
    return f ? le(p) : p;
  }
  let h = s;
  o !== e && (f ? h = function(p, S) {
    return s.call(this, le(p), S, e);
  } : s.length > 2 && (h = function(p, S) {
    return s.call(this, p, S, e);
  }));
  const a = u.call(o, h, n);
  return f && r ? r(a) : a;
}
function qs(e, t, s, n) {
  const r = Os(e);
  let i = s;
  return r !== e && (ye(e) ? s.length > 3 && (i = function(o, f, u) {
    return s.call(this, o, f, u, e);
  }) : i = function(o, f, u) {
    return s.call(this, o, le(f), u, e);
  }), r[t](i, ...n);
}
function es(e, t, s) {
  const n = H(e);
  z(n, "iterate", gt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && Is(s[0]) ? (s[0] = H(s[0]), n[t](...s)) : r;
}
function rt(e, t, s = []) {
  De(), Ts();
  const n = H(e)[t].apply(e, s);
  return Cs(), je(), n;
}
const Br = /* @__PURE__ */ bs("__proto__,__v_isRef,__isVue"), Hn = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Fe)
);
function Kr(e) {
  Fe(e) || (e = String(e));
  const t = H(this);
  return z(t, "has", e), t.hasOwnProperty(e);
}
class $n {
  constructor(t = !1, s = !1) {
    this._isReadonly = t, this._isShallow = s;
  }
  get(t, s, n) {
    if (s === "__v_skip") return t.__v_skip;
    const r = this._isReadonly, i = this._isShallow;
    if (s === "__v_isReactive")
      return !r;
    if (s === "__v_isReadonly")
      return r;
    if (s === "__v_isShallow")
      return i;
    if (s === "__v_raw")
      return n === (r ? i ? kr : Vn : i ? Un : Ln).get(t) || // receiver is not the reactive proxy, but has the same prototype
      // this means the receiver is a user proxy of the reactive proxy
      Object.getPrototypeOf(t) === Object.getPrototypeOf(n) ? t : void 0;
    const o = P(t);
    if (!r) {
      let u;
      if (o && (u = Ur[s]))
        return u;
      if (s === "hasOwnProperty")
        return Kr;
    }
    const f = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      ee(t) ? t : n
    );
    return (Fe(s) ? Hn.has(s) : Br(s)) || (r || z(t, "get", s), i) ? f : ee(f) ? o && vs(s) ? f : f.value : q(f) ? r ? Bn(f) : Ps(f) : f;
  }
}
class Nn extends $n {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const u = Qe(i);
      if (!ye(n) && !Qe(n) && (i = H(i), n = H(n)), !P(t) && ee(i) && !ee(n))
        return u ? !1 : (i.value = n, !0);
    }
    const o = P(t) && vs(s) ? Number(s) < t.length : D(t, s), f = Reflect.set(
      t,
      s,
      n,
      ee(t) ? t : r
    );
    return t === H(r) && (o ? Be(n, i) && Ce(t, "set", s, n) : Ce(t, "add", s, n)), f;
  }
  deleteProperty(t, s) {
    const n = D(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Ce(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!Fe(s) || !Hn.has(s)) && z(t, "has", s), n;
  }
  ownKeys(t) {
    return z(
      t,
      "iterate",
      P(t) ? "length" : Ke
    ), Reflect.ownKeys(t);
  }
}
class Wr extends $n {
  constructor(t = !1) {
    super(!0, t);
  }
  set(t, s) {
    return !0;
  }
  deleteProperty(t, s) {
    return !0;
  }
}
const qr = /* @__PURE__ */ new Nn(), Jr = /* @__PURE__ */ new Wr(), Gr = /* @__PURE__ */ new Nn(!0);
const us = (e) => e, Ot = (e) => Reflect.getPrototypeOf(e);
function Yr(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = H(r), o = ze(i), f = e === "entries" || e === Symbol.iterator && o, u = e === "keys" && o, h = r[e](...n), a = s ? us : t ? as : le;
    return !t && z(
      i,
      "iterate",
      u ? cs : Ke
    ), {
      // iterator protocol
      next() {
        const { value: p, done: S } = h.next();
        return S ? { value: p, done: S } : {
          value: f ? [a(p[0]), a(p[1])] : a(p),
          done: S
        };
      },
      // iterable protocol
      [Symbol.iterator]() {
        return this;
      }
    };
  };
}
function At(e) {
  return function(...t) {
    return e === "delete" ? !1 : e === "clear" ? void 0 : this;
  };
}
function zr(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = H(i), f = H(r);
      e || (Be(r, f) && z(o, "get", r), z(o, "get", f));
      const { has: u } = Ot(o), h = t ? us : e ? as : le;
      if (u.call(o, r))
        return h(i.get(r));
      if (u.call(o, f))
        return h(i.get(f));
      i !== o && i.get(r);
    },
    get size() {
      const r = this.__v_raw;
      return !e && z(H(r), "iterate", Ke), Reflect.get(r, "size", r);
    },
    has(r) {
      const i = this.__v_raw, o = H(i), f = H(r);
      return e || (Be(r, f) && z(o, "has", r), z(o, "has", f)), r === f ? i.has(r) : i.has(r) || i.has(f);
    },
    forEach(r, i) {
      const o = this, f = o.__v_raw, u = H(f), h = t ? us : e ? as : le;
      return !e && z(u, "iterate", Ke), f.forEach((a, p) => r.call(i, h(a), h(p), o));
    }
  };
  return te(
    s,
    e ? {
      add: At("add"),
      set: At("set"),
      delete: At("delete"),
      clear: At("clear")
    } : {
      add(r) {
        !t && !ye(r) && !Qe(r) && (r = H(r));
        const i = H(this);
        return Ot(i).has.call(i, r) || (i.add(r), Ce(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !ye(i) && !Qe(i) && (i = H(i));
        const o = H(this), { has: f, get: u } = Ot(o);
        let h = f.call(o, r);
        h || (r = H(r), h = f.call(o, r));
        const a = u.call(o, r);
        return o.set(r, i), h ? Be(i, a) && Ce(o, "set", r, i) : Ce(o, "add", r, i), this;
      },
      delete(r) {
        const i = H(this), { has: o, get: f } = Ot(i);
        let u = o.call(i, r);
        u || (r = H(r), u = o.call(i, r)), f && f.call(i, r);
        const h = i.delete(r);
        return u && Ce(i, "delete", r, void 0), h;
      },
      clear() {
        const r = H(this), i = r.size !== 0, o = r.clear();
        return i && Ce(
          r,
          "clear",
          void 0,
          void 0
        ), o;
      }
    }
  ), [
    "keys",
    "values",
    "entries",
    Symbol.iterator
  ].forEach((r) => {
    s[r] = Yr(r, e, t);
  }), s;
}
function As(e, t) {
  const s = zr(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    D(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Xr = {
  get: /* @__PURE__ */ As(!1, !1)
}, Zr = {
  get: /* @__PURE__ */ As(!1, !0)
}, Qr = {
  get: /* @__PURE__ */ As(!0, !1)
};
const Ln = /* @__PURE__ */ new WeakMap(), Un = /* @__PURE__ */ new WeakMap(), Vn = /* @__PURE__ */ new WeakMap(), kr = /* @__PURE__ */ new WeakMap();
function ei(e) {
  switch (e) {
    case "Object":
    case "Array":
      return 1;
    case "Map":
    case "Set":
    case "WeakMap":
    case "WeakSet":
      return 2;
    default:
      return 0;
  }
}
function ti(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : ei(Er(e));
}
function Ps(e) {
  return Qe(e) ? e : Rs(
    e,
    !1,
    qr,
    Xr,
    Ln
  );
}
function si(e) {
  return Rs(
    e,
    !1,
    Gr,
    Zr,
    Un
  );
}
function Bn(e) {
  return Rs(
    e,
    !0,
    Jr,
    Qr,
    Vn
  );
}
function Rs(e, t, s, n, r) {
  if (!q(e) || e.__v_raw && !(t && e.__v_isReactive))
    return e;
  const i = r.get(e);
  if (i)
    return i;
  const o = ti(e);
  if (o === 0)
    return e;
  const f = new Proxy(
    e,
    o === 2 ? n : s
  );
  return r.set(e, f), f;
}
function ut(e) {
  return Qe(e) ? ut(e.__v_raw) : !!(e && e.__v_isReactive);
}
function Qe(e) {
  return !!(e && e.__v_isReadonly);
}
function ye(e) {
  return !!(e && e.__v_isShallow);
}
function Is(e) {
  return e ? !!e.__v_raw : !1;
}
function H(e) {
  const t = e && e.__v_raw;
  return t ? H(t) : e;
}
function ni(e) {
  return !D(e, "__v_skip") && Object.isExtensible(e) && wn(e, "__v_skip", !0), e;
}
const le = (e) => q(e) ? Ps(e) : e, as = (e) => q(e) ? Bn(e) : e;
function ee(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function ri(e) {
  return ee(e) ? e.value : e;
}
const ii = {
  get: (e, t, s) => t === "__v_raw" ? e : ri(Reflect.get(e, t, s)),
  set: (e, t, s, n) => {
    const r = e[t];
    return ee(r) && !ee(s) ? (r.value = s, !0) : Reflect.set(e, t, s, n);
  }
};
function Kn(e) {
  return ut(e) ? e : new Proxy(e, ii);
}
class oi {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Dn(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = pt - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    U !== this)
      return Pn(this, !0), !0;
  }
  get value() {
    const t = this.dep.track();
    return Mn(this), t && (t.version = this.dep.version), this._value;
  }
  set value(t) {
    this.setter && this.setter(t);
  }
}
function li(e, t, s = !1) {
  let n, r;
  return R(e) ? n = e : (n = e.get, r = e.set), new oi(n, r, s);
}
const Pt = {}, Ft = /* @__PURE__ */ new WeakMap();
let Ve;
function fi(e, t = !1, s = Ve) {
  if (s) {
    let n = Ft.get(s);
    n || Ft.set(s, n = []), n.push(e);
  }
}
function ci(e, t, s = V) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: f, call: u } = s, h = (O) => r ? O : ye(O) || r === !1 || r === 0 ? Ie(O, 1) : Ie(O);
  let a, p, S, T, F = !1, M = !1;
  if (ee(e) ? (p = () => e.value, F = ye(e)) : ut(e) ? (p = () => h(e), F = !0) : P(e) ? (M = !0, F = e.some((O) => ut(O) || ye(O)), p = () => e.map((O) => {
    if (ee(O))
      return O.value;
    if (ut(O))
      return h(O);
    if (R(O))
      return u ? u(O, 2) : O();
  })) : R(e) ? t ? p = u ? () => u(e, 2) : e : p = () => {
    if (S) {
      De();
      try {
        S();
      } finally {
        je();
      }
    }
    const O = Ve;
    Ve = a;
    try {
      return u ? u(e, 3, [T]) : e(T);
    } finally {
      Ve = O;
    }
  } : p = xe, t && r) {
    const O = p, J = r === !0 ? 1 / 0 : r;
    p = () => Ie(O(), J);
  }
  const Y = $r(), $ = () => {
    a.stop(), Y && Y.active && ys(Y.effects, a);
  };
  if (i && t) {
    const O = t;
    t = (...J) => {
      O(...J), $();
    };
  }
  let K = M ? new Array(e.length).fill(Pt) : Pt;
  const W = (O) => {
    if (!(!(a.flags & 1) || !a.dirty && !O))
      if (t) {
        const J = a.run();
        if (r || F || (M ? J.some((Oe, ue) => Be(Oe, K[ue])) : Be(J, K))) {
          S && S();
          const Oe = Ve;
          Ve = a;
          try {
            const ue = [
              J,
              // pass undefined as the old value when it's changed for the first time
              K === Pt ? void 0 : M && K[0] === Pt ? [] : K,
              T
            ];
            u ? u(t, 3, ue) : (
              // @ts-expect-error
              t(...ue)
            ), K = J;
          } finally {
            Ve = Oe;
          }
        }
      } else
        a.run();
  };
  return f && f(W), a = new On(p), a.scheduler = o ? () => o(W, !1) : W, T = (O) => fi(O, !1, a), S = a.onStop = () => {
    const O = Ft.get(a);
    if (O) {
      if (u)
        u(O, 4);
      else
        for (const J of O) J();
      Ft.delete(a);
    }
  }, t ? n ? W(!0) : K = a.run() : o ? o(W.bind(null, !0), !0) : a.run(), $.pause = a.pause.bind(a), $.resume = a.resume.bind(a), $.stop = $, $;
}
function Ie(e, t = 1 / 0, s) {
  if (t <= 0 || !q(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ee(e))
    Ie(e.value, t, s);
  else if (P(e))
    for (let n = 0; n < e.length; n++)
      Ie(e[n], t, s);
  else if (mn(e) || ze(e))
    e.forEach((n) => {
      Ie(n, t, s);
    });
  else if (yn(e)) {
    for (const n in e)
      Ie(e[n], t, s);
    for (const n of Object.getOwnPropertySymbols(e))
      Object.prototype.propertyIsEnumerable.call(e, n) && Ie(e[n], t, s);
  }
  return e;
}
/**
* @vue/runtime-core v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
function yt(e, t, s, n) {
  try {
    return n ? e(...n) : e();
  } catch (r) {
    Kt(r, t, s);
  }
}
function ve(e, t, s, n) {
  if (R(e)) {
    const r = yt(e, t, s, n);
    return r && bn(r) && r.catch((i) => {
      Kt(i, t, s);
    }), r;
  }
  if (P(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(ve(e[i], t, s, n));
    return r;
  }
}
function Kt(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || V;
  if (t) {
    let f = t.parent;
    const u = t.proxy, h = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; f; ) {
      const a = f.ec;
      if (a) {
        for (let p = 0; p < a.length; p++)
          if (a[p](e, u, h) === !1)
            return;
      }
      f = f.parent;
    }
    if (i) {
      De(), yt(i, null, 10, [
        e,
        u,
        h
      ]), je();
      return;
    }
  }
  ui(e, s, r, n, o);
}
function ui(e, t, s, n = !0, r = !1) {
  if (r)
    throw e;
  console.error(e);
}
const Q = [];
let _e = -1;
const Xe = [];
let Pe = null, Ge = 0;
const Wn = /* @__PURE__ */ Promise.resolve();
let Dt = null;
function ai(e) {
  const t = Dt || Wn;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function di(e) {
  let t = _e + 1, s = Q.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = Q[n], i = _t(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function Ms(e) {
  if (!(e.flags & 1)) {
    const t = _t(e), s = Q[Q.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= _t(s) ? Q.push(e) : Q.splice(di(t), 0, e), e.flags |= 1, qn();
  }
}
function qn() {
  Dt || (Dt = Wn.then(Gn));
}
function hi(e) {
  P(e) ? Xe.push(...e) : Pe && e.id === -1 ? Pe.splice(Ge + 1, 0, e) : e.flags & 1 || (Xe.push(e), e.flags |= 1), qn();
}
function Js(e, t, s = _e + 1) {
  for (; s < Q.length; s++) {
    const n = Q[s];
    if (n && n.flags & 2) {
      if (e && n.id !== e.uid)
        continue;
      Q.splice(s, 1), s--, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
    }
  }
}
function Jn(e) {
  if (Xe.length) {
    const t = [...new Set(Xe)].sort(
      (s, n) => _t(s) - _t(n)
    );
    if (Xe.length = 0, Pe) {
      Pe.push(...t);
      return;
    }
    for (Pe = t, Ge = 0; Ge < Pe.length; Ge++) {
      const s = Pe[Ge];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    Pe = null, Ge = 0;
  }
}
const _t = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function Gn(e) {
  try {
    for (_e = 0; _e < Q.length; _e++) {
      const t = Q[_e];
      t && !(t.flags & 8) && (t.flags & 4 && (t.flags &= -2), yt(
        t,
        t.i,
        t.i ? 15 : 14
      ), t.flags & 4 || (t.flags &= -2));
    }
  } finally {
    for (; _e < Q.length; _e++) {
      const t = Q[_e];
      t && (t.flags &= -2);
    }
    _e = -1, Q.length = 0, Jn(), Dt = null, (Q.length || Xe.length) && Gn();
  }
}
let be = null, Yn = null;
function jt(e) {
  const t = be;
  return be = e, Yn = e && e.type.__scopeId || null, t;
}
function pi(e, t = be, s) {
  if (!t || e._n)
    return e;
  const n = (...r) => {
    n._d && tn(-1);
    const i = jt(t);
    let o;
    try {
      o = e(...r);
    } finally {
      jt(i), n._d && tn(1);
    }
    return o;
  };
  return n._n = !0, n._c = !0, n._d = !0, n;
}
function Le(e, t, s, n) {
  const r = e.dirs, i = t && t.dirs;
  for (let o = 0; o < r.length; o++) {
    const f = r[o];
    i && (f.oldValue = i[o].value);
    let u = f.dir[n];
    u && (De(), ve(u, s, 8, [
      e.el,
      f,
      e,
      t
    ]), je());
  }
}
const gi = Symbol("_vte"), _i = (e) => e.__isTeleport;
function Fs(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, Fs(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
function zn(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function Ht(e, t, s, n, r = !1) {
  if (P(e)) {
    e.forEach(
      (F, M) => Ht(
        F,
        t && (P(t) ? t[M] : t),
        s,
        n,
        r
      )
    );
    return;
  }
  if (at(n) && !r) {
    n.shapeFlag & 512 && n.type.__asyncResolved && n.component.subTree.component && Ht(e, t, s, n.component.subTree);
    return;
  }
  const i = n.shapeFlag & 4 ? $s(n.component) : n.el, o = r ? null : i, { i: f, r: u } = e, h = t && t.r, a = f.refs === V ? f.refs = {} : f.refs, p = f.setupState, S = H(p), T = p === V ? () => !1 : (F) => D(S, F);
  if (h != null && h !== u && (G(h) ? (a[h] = null, T(h) && (p[h] = null)) : ee(h) && (h.value = null)), R(u))
    yt(u, f, 12, [o, a]);
  else {
    const F = G(u), M = ee(u);
    if (F || M) {
      const Y = () => {
        if (e.f) {
          const $ = F ? T(u) ? p[u] : a[u] : u.value;
          r ? P($) && ys($, i) : P($) ? $.includes(i) || $.push(i) : F ? (a[u] = [i], T(u) && (p[u] = a[u])) : (u.value = [i], e.k && (a[e.k] = u.value));
        } else F ? (a[u] = o, T(u) && (p[u] = o)) : M && (u.value = o, e.k && (a[e.k] = o));
      };
      o ? (Y.id = -1, ie(Y, s)) : Y();
    }
  }
}
Bt().requestIdleCallback;
Bt().cancelIdleCallback;
const at = (e) => !!e.type.__asyncLoader, Xn = (e) => e.type.__isKeepAlive;
function mi(e, t) {
  Zn(e, "a", t);
}
function bi(e, t) {
  Zn(e, "da", t);
}
function Zn(e, t, s = k) {
  const n = e.__wdc || (e.__wdc = () => {
    let r = s;
    for (; r; ) {
      if (r.isDeactivated)
        return;
      r = r.parent;
    }
    return e();
  });
  if (Wt(t, n, s), s) {
    let r = s.parent;
    for (; r && r.parent; )
      Xn(r.parent.vnode) && xi(n, t, s, r), r = r.parent;
  }
}
function xi(e, t, s, n) {
  const r = Wt(
    t,
    e,
    n,
    !0
    /* prepend */
  );
  Qn(() => {
    ys(n[t], r);
  }, s);
}
function Wt(e, t, s = k, n = !1) {
  if (s) {
    const r = s[e] || (s[e] = []), i = t.__weh || (t.__weh = (...o) => {
      De();
      const f = vt(s), u = ve(t, s, e, o);
      return f(), je(), u;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const Ee = (e) => (t, s = k) => {
  (!xt || e === "sp") && Wt(e, (...n) => t(...n), s);
}, yi = Ee("bm"), vi = Ee("m"), wi = Ee(
  "bu"
), Si = Ee("u"), Ti = Ee(
  "bum"
), Qn = Ee("um"), Ci = Ee(
  "sp"
), Ei = Ee("rtg"), Oi = Ee("rtc");
function Ai(e, t = k) {
  Wt("ec", e, t);
}
const Pi = Symbol.for("v-ndc"), ds = (e) => e ? xr(e) ? $s(e) : ds(e.parent) : null, dt = (
  // Move PURE marker to new line to workaround compiler discarding it
  // due to type annotation
  /* @__PURE__ */ te(/* @__PURE__ */ Object.create(null), {
    $: (e) => e,
    $el: (e) => e.vnode.el,
    $data: (e) => e.data,
    $props: (e) => e.props,
    $attrs: (e) => e.attrs,
    $slots: (e) => e.slots,
    $refs: (e) => e.refs,
    $parent: (e) => ds(e.parent),
    $root: (e) => ds(e.root),
    $host: (e) => e.ce,
    $emit: (e) => e.emit,
    $options: (e) => er(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      Ms(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = ai.bind(e.proxy)),
    $watch: (e) => Zi.bind(e)
  })
), ts = (e, t) => e !== V && !e.__isScriptSetup && D(e, t), Ri = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: f, appContext: u } = e;
    let h;
    if (t[0] !== "$") {
      const T = o[t];
      if (T !== void 0)
        switch (T) {
          case 1:
            return n[t];
          case 2:
            return r[t];
          case 4:
            return s[t];
          case 3:
            return i[t];
        }
      else {
        if (ts(n, t))
          return o[t] = 1, n[t];
        if (r !== V && D(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (h = e.propsOptions[0]) && D(h, t)
        )
          return o[t] = 3, i[t];
        if (s !== V && D(s, t))
          return o[t] = 4, s[t];
        hs && (o[t] = 0);
      }
    }
    const a = dt[t];
    let p, S;
    if (a)
      return t === "$attrs" && z(e.attrs, "get", ""), a(e);
    if (
      // css module (injected by vue-loader)
      (p = f.__cssModules) && (p = p[t])
    )
      return p;
    if (s !== V && D(s, t))
      return o[t] = 4, s[t];
    if (
      // global properties
      S = u.config.globalProperties, D(S, t)
    )
      return S[t];
  },
  set({ _: e }, t, s) {
    const { data: n, setupState: r, ctx: i } = e;
    return ts(r, t) ? (r[t] = s, !0) : n !== V && D(n, t) ? (n[t] = s, !0) : D(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let f;
    return !!s[o] || e !== V && D(e, o) || ts(t, o) || (f = i[0]) && D(f, o) || D(n, o) || D(dt, o) || D(r.config.globalProperties, o);
  },
  defineProperty(e, t, s) {
    return s.get != null ? e._.accessCache[t] = 0 : D(s, "value") && this.set(e, t, s.value, null), Reflect.defineProperty(e, t, s);
  }
};
function Gs(e) {
  return P(e) ? e.reduce(
    (t, s) => (t[s] = null, t),
    {}
  ) : e;
}
let hs = !0;
function Ii(e) {
  const t = er(e), s = e.proxy, n = e.ctx;
  hs = !1, t.beforeCreate && Ys(t.beforeCreate, e, "bc");
  const {
    // state
    data: r,
    computed: i,
    methods: o,
    watch: f,
    provide: u,
    inject: h,
    // lifecycle
    created: a,
    beforeMount: p,
    mounted: S,
    beforeUpdate: T,
    updated: F,
    activated: M,
    deactivated: Y,
    beforeDestroy: $,
    beforeUnmount: K,
    destroyed: W,
    unmounted: O,
    render: J,
    renderTracked: Oe,
    renderTriggered: ue,
    errorCaptured: Ae,
    serverPrefetch: wt,
    // public API
    expose: He,
    inheritAttrs: et,
    // assets
    components: St,
    directives: Tt,
    filters: Gt
  } = t;
  if (h && Mi(h, n, null), o)
    for (const B in o) {
      const N = o[B];
      R(N) && (n[B] = N.bind(s));
    }
  if (r) {
    const B = r.call(s, s);
    q(B) && (e.data = Ps(B));
  }
  if (hs = !0, i)
    for (const B in i) {
      const N = i[B], $e = R(N) ? N.bind(s, s) : R(N.get) ? N.get.bind(s, s) : xe, Ct = !R(N) && R(N.set) ? N.set.bind(s) : xe, Ne = wo({
        get: $e,
        set: Ct
      });
      Object.defineProperty(n, B, {
        enumerable: !0,
        configurable: !0,
        get: () => Ne.value,
        set: (ae) => Ne.value = ae
      });
    }
  if (f)
    for (const B in f)
      kn(f[B], n, s, B);
  if (u) {
    const B = R(u) ? u.call(s) : u;
    Reflect.ownKeys(B).forEach((N) => {
      Ni(N, B[N]);
    });
  }
  a && Ys(a, e, "c");
  function X(B, N) {
    P(N) ? N.forEach(($e) => B($e.bind(s))) : N && B(N.bind(s));
  }
  if (X(yi, p), X(vi, S), X(wi, T), X(Si, F), X(mi, M), X(bi, Y), X(Ai, Ae), X(Oi, Oe), X(Ei, ue), X(Ti, K), X(Qn, O), X(Ci, wt), P(He))
    if (He.length) {
      const B = e.exposed || (e.exposed = {});
      He.forEach((N) => {
        Object.defineProperty(B, N, {
          get: () => s[N],
          set: ($e) => s[N] = $e
        });
      });
    } else e.exposed || (e.exposed = {});
  J && e.render === xe && (e.render = J), et != null && (e.inheritAttrs = et), St && (e.components = St), Tt && (e.directives = Tt), wt && zn(e);
}
function Mi(e, t, s = xe) {
  P(e) && (e = ps(e));
  for (const n in e) {
    const r = e[n];
    let i;
    q(r) ? "default" in r ? i = Rt(
      r.from || n,
      r.default,
      !0
    ) : i = Rt(r.from || n) : i = Rt(r), ee(i) ? Object.defineProperty(t, n, {
      enumerable: !0,
      configurable: !0,
      get: () => i.value,
      set: (o) => i.value = o
    }) : t[n] = i;
  }
}
function Ys(e, t, s) {
  ve(
    P(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function kn(e, t, s, n) {
  let r = n.includes(".") ? pr(s, n) : () => s[n];
  if (G(e)) {
    const i = t[e];
    R(i) && ns(r, i);
  } else if (R(e))
    ns(r, e.bind(s));
  else if (q(e))
    if (P(e))
      e.forEach((i) => kn(i, t, s, n));
    else {
      const i = R(e.handler) ? e.handler.bind(s) : t[e.handler];
      R(i) && ns(r, i, e);
    }
}
function er(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, f = i.get(t);
  let u;
  return f ? u = f : !r.length && !s && !n ? u = t : (u = {}, r.length && r.forEach(
    (h) => $t(u, h, o, !0)
  ), $t(u, t, o)), q(t) && i.set(t, u), u;
}
function $t(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && $t(e, i, s, !0), r && r.forEach(
    (o) => $t(e, o, s, !0)
  );
  for (const o in t)
    if (!(n && o === "expose")) {
      const f = Fi[o] || s && s[o];
      e[o] = f ? f(e[o], t[o]) : t[o];
    }
  return e;
}
const Fi = {
  data: zs,
  props: Xs,
  emits: Xs,
  // objects
  methods: ot,
  computed: ot,
  // lifecycle
  beforeCreate: Z,
  created: Z,
  beforeMount: Z,
  mounted: Z,
  beforeUpdate: Z,
  updated: Z,
  beforeDestroy: Z,
  beforeUnmount: Z,
  destroyed: Z,
  unmounted: Z,
  activated: Z,
  deactivated: Z,
  errorCaptured: Z,
  serverPrefetch: Z,
  // assets
  components: ot,
  directives: ot,
  // watch
  watch: ji,
  // provide / inject
  provide: zs,
  inject: Di
};
function zs(e, t) {
  return t ? e ? function() {
    return te(
      R(e) ? e.call(this, this) : e,
      R(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function Di(e, t) {
  return ot(ps(e), ps(t));
}
function ps(e) {
  if (P(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++)
      t[e[s]] = e[s];
    return t;
  }
  return e;
}
function Z(e, t) {
  return e ? [...new Set([].concat(e, t))] : t;
}
function ot(e, t) {
  return e ? te(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function Xs(e, t) {
  return e ? P(e) && P(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : te(
    /* @__PURE__ */ Object.create(null),
    Gs(e),
    Gs(t ?? {})
  ) : t;
}
function ji(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = te(/* @__PURE__ */ Object.create(null), e);
  for (const n in t)
    s[n] = Z(e[n], t[n]);
  return s;
}
function tr() {
  return {
    app: null,
    config: {
      isNativeTag: Tr,
      performance: !1,
      globalProperties: {},
      optionMergeStrategies: {},
      errorHandler: void 0,
      warnHandler: void 0,
      compilerOptions: {}
    },
    mixins: [],
    components: {},
    directives: {},
    provides: /* @__PURE__ */ Object.create(null),
    optionsCache: /* @__PURE__ */ new WeakMap(),
    propsCache: /* @__PURE__ */ new WeakMap(),
    emitsCache: /* @__PURE__ */ new WeakMap()
  };
}
let Hi = 0;
function $i(e, t) {
  return function(n, r = null) {
    R(n) || (n = te({}, n)), r != null && !q(r) && (r = null);
    const i = tr(), o = /* @__PURE__ */ new WeakSet(), f = [];
    let u = !1;
    const h = i.app = {
      _uid: Hi++,
      _component: n,
      _props: r,
      _container: null,
      _context: i,
      _instance: null,
      version: So,
      get config() {
        return i.config;
      },
      set config(a) {
      },
      use(a, ...p) {
        return o.has(a) || (a && R(a.install) ? (o.add(a), a.install(h, ...p)) : R(a) && (o.add(a), a(h, ...p))), h;
      },
      mixin(a) {
        return i.mixins.includes(a) || i.mixins.push(a), h;
      },
      component(a, p) {
        return p ? (i.components[a] = p, h) : i.components[a];
      },
      directive(a, p) {
        return p ? (i.directives[a] = p, h) : i.directives[a];
      },
      mount(a, p, S) {
        if (!u) {
          const T = h._ceVNode || We(n, r);
          return T.appContext = i, S === !0 ? S = "svg" : S === !1 && (S = void 0), e(T, a, S), u = !0, h._container = a, a.__vue_app__ = h, $s(T.component);
        }
      },
      onUnmount(a) {
        f.push(a);
      },
      unmount() {
        u && (ve(
          f,
          h._instance,
          16
        ), e(null, h._container), delete h._container.__vue_app__);
      },
      provide(a, p) {
        return i.provides[a] = p, h;
      },
      runWithContext(a) {
        const p = Ze;
        Ze = h;
        try {
          return a();
        } finally {
          Ze = p;
        }
      }
    };
    return h;
  };
}
let Ze = null;
function Ni(e, t) {
  if (k) {
    let s = k.provides;
    const n = k.parent && k.parent.provides;
    n === s && (s = k.provides = Object.create(n)), s[e] = t;
  }
}
function Rt(e, t, s = !1) {
  const n = k || be;
  if (n || Ze) {
    const r = Ze ? Ze._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && R(t) ? t.call(n && n.proxy) : t;
  }
}
const sr = {}, nr = () => Object.create(sr), rr = (e) => Object.getPrototypeOf(e) === sr;
function Li(e, t, s, n = !1) {
  const r = {}, i = nr();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), ir(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : si(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function Ui(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, f = H(r), [u] = e.propsOptions;
  let h = !1;
  if (
    // always force full diff in dev
    // - #1942 if hmr is enabled with sfc component
    // - vite#872 non-sfc component used by sfc component
    (n || o > 0) && !(o & 16)
  ) {
    if (o & 8) {
      const a = e.vnode.dynamicProps;
      for (let p = 0; p < a.length; p++) {
        let S = a[p];
        if (qt(e.emitsOptions, S))
          continue;
        const T = t[S];
        if (u)
          if (D(i, S))
            T !== i[S] && (i[S] = T, h = !0);
          else {
            const F = Me(S);
            r[F] = gs(
              u,
              f,
              F,
              T,
              e,
              !1
            );
          }
        else
          T !== i[S] && (i[S] = T, h = !0);
      }
    }
  } else {
    ir(e, t, r, i) && (h = !0);
    let a;
    for (const p in f)
      (!t || // for camelCase
      !D(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((a = qe(p)) === p || !D(t, a))) && (u ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[a] !== void 0) && (r[p] = gs(
        u,
        f,
        p,
        void 0,
        e,
        !0
      )) : delete r[p]);
    if (i !== f)
      for (const p in i)
        (!t || !D(t, p)) && (delete i[p], h = !0);
  }
  h && Ce(e.attrs, "set", "");
}
function ir(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, f;
  if (t)
    for (let u in t) {
      if (lt(u))
        continue;
      const h = t[u];
      let a;
      r && D(r, a = Me(u)) ? !i || !i.includes(a) ? s[a] = h : (f || (f = {}))[a] = h : qt(e.emitsOptions, u) || (!(u in n) || h !== n[u]) && (n[u] = h, o = !0);
    }
  if (i) {
    const u = H(s), h = f || V;
    for (let a = 0; a < i.length; a++) {
      const p = i[a];
      s[p] = gs(
        r,
        u,
        p,
        h[p],
        e,
        !D(h, p)
      );
    }
  }
  return o;
}
function gs(e, t, s, n, r, i) {
  const o = e[s];
  if (o != null) {
    const f = D(o, "default");
    if (f && n === void 0) {
      const u = o.default;
      if (o.type !== Function && !o.skipFactory && R(u)) {
        const { propsDefaults: h } = r;
        if (s in h)
          n = h[s];
        else {
          const a = vt(r);
          n = h[s] = u.call(
            null,
            t
          ), a();
        }
      } else
        n = u;
      r.ce && r.ce._setProp(s, n);
    }
    o[
      0
      /* shouldCast */
    ] && (i && !f ? n = !1 : o[
      1
      /* shouldCastTrue */
    ] && (n === "" || n === qe(s)) && (n = !0));
  }
  return n;
}
const Vi = /* @__PURE__ */ new WeakMap();
function or(e, t, s = !1) {
  const n = s ? Vi : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, f = [];
  let u = !1;
  if (!R(e)) {
    const a = (p) => {
      u = !0;
      const [S, T] = or(p, t, !0);
      te(o, S), T && f.push(...T);
    };
    !s && t.mixins.length && t.mixins.forEach(a), e.extends && a(e.extends), e.mixins && e.mixins.forEach(a);
  }
  if (!i && !u)
    return q(e) && n.set(e, Ye), Ye;
  if (P(i))
    for (let a = 0; a < i.length; a++) {
      const p = Me(i[a]);
      Zs(p) && (o[p] = V);
    }
  else if (i)
    for (const a in i) {
      const p = Me(a);
      if (Zs(p)) {
        const S = i[a], T = o[p] = P(S) || R(S) ? { type: S } : te({}, S), F = T.type;
        let M = !1, Y = !0;
        if (P(F))
          for (let $ = 0; $ < F.length; ++$) {
            const K = F[$], W = R(K) && K.name;
            if (W === "Boolean") {
              M = !0;
              break;
            } else W === "String" && (Y = !1);
          }
        else
          M = R(F) && F.name === "Boolean";
        T[
          0
          /* shouldCast */
        ] = M, T[
          1
          /* shouldCastTrue */
        ] = Y, (M || D(T, "default")) && f.push(p);
      }
    }
  const h = [o, f];
  return q(e) && n.set(e, h), h;
}
function Zs(e) {
  return e[0] !== "$" && !lt(e);
}
const lr = (e) => e[0] === "_" || e === "$stable", Ds = (e) => P(e) ? e.map(me) : [me(e)], Bi = (e, t, s) => {
  if (t._n)
    return t;
  const n = pi((...r) => Ds(t(...r)), s);
  return n._c = !1, n;
}, fr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (lr(r)) continue;
    const i = e[r];
    if (R(i))
      t[r] = Bi(r, i, n);
    else if (i != null) {
      const o = Ds(i);
      t[r] = () => o;
    }
  }
}, cr = (e, t) => {
  const s = Ds(t);
  e.slots.default = () => s;
}, ur = (e, t, s) => {
  for (const n in t)
    (s || n !== "_") && (e[n] = t[n]);
}, Ki = (e, t, s) => {
  const n = e.slots = nr();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (ur(n, t, s), s && wn(n, "_", r, !0)) : fr(t, n);
  } else t && cr(e, t);
}, Wi = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = V;
  if (n.shapeFlag & 32) {
    const f = t._;
    f ? s && f === 1 ? i = !1 : ur(r, t, s) : (i = !t.$stable, fr(t, r)), o = t;
  } else t && (cr(e, t), o = { default: 1 });
  if (i)
    for (const f in r)
      !lr(f) && o[f] == null && delete r[f];
}, ie = ro;
function qi(e) {
  return Ji(e);
}
function Ji(e, t) {
  const s = Bt();
  s.__VUE__ = !0;
  const {
    insert: n,
    remove: r,
    patchProp: i,
    createElement: o,
    createText: f,
    createComment: u,
    setText: h,
    setElementText: a,
    parentNode: p,
    nextSibling: S,
    setScopeId: T = xe,
    insertStaticContent: F
  } = e, M = (l, c, d, m = null, g = null, _ = null, v = void 0, y = null, x = !!c.dynamicChildren) => {
    if (l === c)
      return;
    l && !it(l, c) && (m = Et(l), ae(l, g, _, !0), l = null), c.patchFlag === -2 && (x = !1, c.dynamicChildren = null);
    const { type: b, ref: E, shapeFlag: w } = c;
    switch (b) {
      case Jt:
        Y(l, c, d, m);
        break;
      case mt:
        $(l, c, d, m);
        break;
      case rs:
        l == null && K(c, d, m, v);
        break;
      case Te:
        St(
          l,
          c,
          d,
          m,
          g,
          _,
          v,
          y,
          x
        );
        break;
      default:
        w & 1 ? J(
          l,
          c,
          d,
          m,
          g,
          _,
          v,
          y,
          x
        ) : w & 6 ? Tt(
          l,
          c,
          d,
          m,
          g,
          _,
          v,
          y,
          x
        ) : (w & 64 || w & 128) && b.process(
          l,
          c,
          d,
          m,
          g,
          _,
          v,
          y,
          x,
          st
        );
    }
    E != null && g && Ht(E, l && l.ref, _, c || l, !c);
  }, Y = (l, c, d, m) => {
    if (l == null)
      n(
        c.el = f(c.children),
        d,
        m
      );
    else {
      const g = c.el = l.el;
      c.children !== l.children && h(g, c.children);
    }
  }, $ = (l, c, d, m) => {
    l == null ? n(
      c.el = u(c.children || ""),
      d,
      m
    ) : c.el = l.el;
  }, K = (l, c, d, m) => {
    [l.el, l.anchor] = F(
      l.children,
      c,
      d,
      m,
      l.el,
      l.anchor
    );
  }, W = ({ el: l, anchor: c }, d, m) => {
    let g;
    for (; l && l !== c; )
      g = S(l), n(l, d, m), l = g;
    n(c, d, m);
  }, O = ({ el: l, anchor: c }) => {
    let d;
    for (; l && l !== c; )
      d = S(l), r(l), l = d;
    r(c);
  }, J = (l, c, d, m, g, _, v, y, x) => {
    c.type === "svg" ? v = "svg" : c.type === "math" && (v = "mathml"), l == null ? Oe(
      c,
      d,
      m,
      g,
      _,
      v,
      y,
      x
    ) : wt(
      l,
      c,
      g,
      _,
      v,
      y,
      x
    );
  }, Oe = (l, c, d, m, g, _, v, y) => {
    let x, b;
    const { props: E, shapeFlag: w, transition: C, dirs: A } = l;
    if (x = l.el = o(
      l.type,
      _,
      E && E.is,
      E
    ), w & 8 ? a(x, l.children) : w & 16 && Ae(
      l.children,
      x,
      null,
      m,
      g,
      ss(l, _),
      v,
      y
    ), A && Le(l, null, m, "created"), ue(x, l, l.scopeId, v, m), E) {
      for (const L in E)
        L !== "value" && !lt(L) && i(x, L, null, E[L], _, m);
      "value" in E && i(x, "value", null, E.value, _), (b = E.onVnodeBeforeMount) && ge(b, m, l);
    }
    A && Le(l, null, m, "beforeMount");
    const I = Gi(g, C);
    I && C.beforeEnter(x), n(x, c, d), ((b = E && E.onVnodeMounted) || I || A) && ie(() => {
      b && ge(b, m, l), I && C.enter(x), A && Le(l, null, m, "mounted");
    }, g);
  }, ue = (l, c, d, m, g) => {
    if (d && T(l, d), m)
      for (let _ = 0; _ < m.length; _++)
        T(l, m[_]);
    if (g) {
      let _ = g.subTree;
      if (c === _ || _r(_.type) && (_.ssContent === c || _.ssFallback === c)) {
        const v = g.vnode;
        ue(
          l,
          v,
          v.scopeId,
          v.slotScopeIds,
          g.parent
        );
      }
    }
  }, Ae = (l, c, d, m, g, _, v, y, x = 0) => {
    for (let b = x; b < l.length; b++) {
      const E = l[b] = y ? Re(l[b]) : me(l[b]);
      M(
        null,
        E,
        c,
        d,
        m,
        g,
        _,
        v,
        y
      );
    }
  }, wt = (l, c, d, m, g, _, v) => {
    const y = c.el = l.el;
    let { patchFlag: x, dynamicChildren: b, dirs: E } = c;
    x |= l.patchFlag & 16;
    const w = l.props || V, C = c.props || V;
    let A;
    if (d && Ue(d, !1), (A = C.onVnodeBeforeUpdate) && ge(A, d, c, l), E && Le(c, l, d, "beforeUpdate"), d && Ue(d, !0), (w.innerHTML && C.innerHTML == null || w.textContent && C.textContent == null) && a(y, ""), b ? He(
      l.dynamicChildren,
      b,
      y,
      d,
      m,
      ss(c, g),
      _
    ) : v || N(
      l,
      c,
      y,
      null,
      d,
      m,
      ss(c, g),
      _,
      !1
    ), x > 0) {
      if (x & 16)
        et(y, w, C, d, g);
      else if (x & 2 && w.class !== C.class && i(y, "class", null, C.class, g), x & 4 && i(y, "style", w.style, C.style, g), x & 8) {
        const I = c.dynamicProps;
        for (let L = 0; L < I.length; L++) {
          const j = I[L], ne = w[j], se = C[j];
          (se !== ne || j === "value") && i(y, j, ne, se, g, d);
        }
      }
      x & 1 && l.children !== c.children && a(y, c.children);
    } else !v && b == null && et(y, w, C, d, g);
    ((A = C.onVnodeUpdated) || E) && ie(() => {
      A && ge(A, d, c, l), E && Le(c, l, d, "updated");
    }, m);
  }, He = (l, c, d, m, g, _, v) => {
    for (let y = 0; y < c.length; y++) {
      const x = l[y], b = c[y], E = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        x.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (x.type === Te || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !it(x, b) || // - In the case of a component, it could contain anything.
        x.shapeFlag & 70) ? p(x.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          d
        )
      );
      M(
        x,
        b,
        E,
        null,
        m,
        g,
        _,
        v,
        !0
      );
    }
  }, et = (l, c, d, m, g) => {
    if (c !== d) {
      if (c !== V)
        for (const _ in c)
          !lt(_) && !(_ in d) && i(
            l,
            _,
            c[_],
            null,
            g,
            m
          );
      for (const _ in d) {
        if (lt(_)) continue;
        const v = d[_], y = c[_];
        v !== y && _ !== "value" && i(l, _, y, v, g, m);
      }
      "value" in d && i(l, "value", c.value, d.value, g);
    }
  }, St = (l, c, d, m, g, _, v, y, x) => {
    const b = c.el = l ? l.el : f(""), E = c.anchor = l ? l.anchor : f("");
    let { patchFlag: w, dynamicChildren: C, slotScopeIds: A } = c;
    A && (y = y ? y.concat(A) : A), l == null ? (n(b, d, m), n(E, d, m), Ae(
      // #10007
      // such fragment like `<></>` will be compiled into
      // a fragment which doesn't have a children.
      // In this case fallback to an empty array
      c.children || [],
      d,
      E,
      g,
      _,
      v,
      y,
      x
    )) : w > 0 && w & 64 && C && // #2715 the previous fragment could've been a BAILed one as a result
    // of renderSlot() with no valid children
    l.dynamicChildren ? (He(
      l.dynamicChildren,
      C,
      d,
      g,
      _,
      v,
      y
    ), // #2080 if the stable fragment has a key, it's a <template v-for> that may
    //  get moved around. Make sure all root level vnodes inherit el.
    // #2134 or if it's a component root, it may also get moved around
    // as the component is being moved.
    (c.key != null || g && c === g.subTree) && ar(
      l,
      c,
      !0
      /* shallow */
    )) : N(
      l,
      c,
      d,
      E,
      g,
      _,
      v,
      y,
      x
    );
  }, Tt = (l, c, d, m, g, _, v, y, x) => {
    c.slotScopeIds = y, l == null ? c.shapeFlag & 512 ? g.ctx.activate(
      c,
      d,
      m,
      v,
      x
    ) : Gt(
      c,
      d,
      m,
      g,
      _,
      v,
      x
    ) : Ns(l, c, x);
  }, Gt = (l, c, d, m, g, _, v) => {
    const y = l.component = _o(
      l,
      m,
      g
    );
    if (Xn(l) && (y.ctx.renderer = st), mo(y, !1, v), y.asyncDep) {
      if (g && g.registerDep(y, X, v), !l.el) {
        const x = y.subTree = We(mt);
        $(null, x, c, d);
      }
    } else
      X(
        y,
        l,
        c,
        d,
        g,
        _,
        v
      );
  }, Ns = (l, c, d) => {
    const m = c.component = l.component;
    if (so(l, c, d))
      if (m.asyncDep && !m.asyncResolved) {
        B(m, c, d);
        return;
      } else
        m.next = c, m.update();
    else
      c.el = l.el, m.vnode = c;
  }, X = (l, c, d, m, g, _, v) => {
    const y = () => {
      if (l.isMounted) {
        let { next: w, bu: C, u: A, parent: I, vnode: L } = l;
        {
          const he = dr(l);
          if (he) {
            w && (w.el = L.el, B(l, w, v)), he.asyncDep.then(() => {
              l.isUnmounted || y();
            });
            return;
          }
        }
        let j = w, ne;
        Ue(l, !1), w ? (w.el = L.el, B(l, w, v)) : w = L, C && Xt(C), (ne = w.props && w.props.onVnodeBeforeUpdate) && ge(ne, I, w, L), Ue(l, !0);
        const se = ks(l), de = l.subTree;
        l.subTree = se, M(
          de,
          se,
          // parent may have changed if it's in a teleport
          p(de.el),
          // anchor may have changed if it's in a fragment
          Et(de),
          l,
          g,
          _
        ), w.el = se.el, j === null && no(l, se.el), A && ie(A, g), (ne = w.props && w.props.onVnodeUpdated) && ie(
          () => ge(ne, I, w, L),
          g
        );
      } else {
        let w;
        const { el: C, props: A } = c, { bm: I, m: L, parent: j, root: ne, type: se } = l, de = at(c);
        Ue(l, !1), I && Xt(I), !de && (w = A && A.onVnodeBeforeMount) && ge(w, j, c), Ue(l, !0);
        {
          ne.ce && ne.ce._injectChildStyle(se);
          const he = l.subTree = ks(l);
          M(
            null,
            he,
            d,
            m,
            l,
            g,
            _
          ), c.el = he.el;
        }
        if (L && ie(L, g), !de && (w = A && A.onVnodeMounted)) {
          const he = c;
          ie(
            () => ge(w, j, he),
            g
          );
        }
        (c.shapeFlag & 256 || j && at(j.vnode) && j.vnode.shapeFlag & 256) && l.a && ie(l.a, g), l.isMounted = !0, c = d = m = null;
      }
    };
    l.scope.on();
    const x = l.effect = new On(y);
    l.scope.off();
    const b = l.update = x.run.bind(x), E = l.job = x.runIfDirty.bind(x);
    E.i = l, E.id = l.uid, x.scheduler = () => Ms(E), Ue(l, !0), b();
  }, B = (l, c, d) => {
    c.component = l;
    const m = l.vnode.props;
    l.vnode = c, l.next = null, Ui(l, c.props, m, d), Wi(l, c.children, d), De(), Js(l), je();
  }, N = (l, c, d, m, g, _, v, y, x = !1) => {
    const b = l && l.children, E = l ? l.shapeFlag : 0, w = c.children, { patchFlag: C, shapeFlag: A } = c;
    if (C > 0) {
      if (C & 128) {
        Ct(
          b,
          w,
          d,
          m,
          g,
          _,
          v,
          y,
          x
        );
        return;
      } else if (C & 256) {
        $e(
          b,
          w,
          d,
          m,
          g,
          _,
          v,
          y,
          x
        );
        return;
      }
    }
    A & 8 ? (E & 16 && tt(b, g, _), w !== b && a(d, w)) : E & 16 ? A & 16 ? Ct(
      b,
      w,
      d,
      m,
      g,
      _,
      v,
      y,
      x
    ) : tt(b, g, _, !0) : (E & 8 && a(d, ""), A & 16 && Ae(
      w,
      d,
      m,
      g,
      _,
      v,
      y,
      x
    ));
  }, $e = (l, c, d, m, g, _, v, y, x) => {
    l = l || Ye, c = c || Ye;
    const b = l.length, E = c.length, w = Math.min(b, E);
    let C;
    for (C = 0; C < w; C++) {
      const A = c[C] = x ? Re(c[C]) : me(c[C]);
      M(
        l[C],
        A,
        d,
        null,
        g,
        _,
        v,
        y,
        x
      );
    }
    b > E ? tt(
      l,
      g,
      _,
      !0,
      !1,
      w
    ) : Ae(
      c,
      d,
      m,
      g,
      _,
      v,
      y,
      x,
      w
    );
  }, Ct = (l, c, d, m, g, _, v, y, x) => {
    let b = 0;
    const E = c.length;
    let w = l.length - 1, C = E - 1;
    for (; b <= w && b <= C; ) {
      const A = l[b], I = c[b] = x ? Re(c[b]) : me(c[b]);
      if (it(A, I))
        M(
          A,
          I,
          d,
          null,
          g,
          _,
          v,
          y,
          x
        );
      else
        break;
      b++;
    }
    for (; b <= w && b <= C; ) {
      const A = l[w], I = c[C] = x ? Re(c[C]) : me(c[C]);
      if (it(A, I))
        M(
          A,
          I,
          d,
          null,
          g,
          _,
          v,
          y,
          x
        );
      else
        break;
      w--, C--;
    }
    if (b > w) {
      if (b <= C) {
        const A = C + 1, I = A < E ? c[A].el : m;
        for (; b <= C; )
          M(
            null,
            c[b] = x ? Re(c[b]) : me(c[b]),
            d,
            I,
            g,
            _,
            v,
            y,
            x
          ), b++;
      }
    } else if (b > C)
      for (; b <= w; )
        ae(l[b], g, _, !0), b++;
    else {
      const A = b, I = b, L = /* @__PURE__ */ new Map();
      for (b = I; b <= C; b++) {
        const re = c[b] = x ? Re(c[b]) : me(c[b]);
        re.key != null && L.set(re.key, b);
      }
      let j, ne = 0;
      const se = C - I + 1;
      let de = !1, he = 0;
      const nt = new Array(se);
      for (b = 0; b < se; b++) nt[b] = 0;
      for (b = A; b <= w; b++) {
        const re = l[b];
        if (ne >= se) {
          ae(re, g, _, !0);
          continue;
        }
        let pe;
        if (re.key != null)
          pe = L.get(re.key);
        else
          for (j = I; j <= C; j++)
            if (nt[j - I] === 0 && it(re, c[j])) {
              pe = j;
              break;
            }
        pe === void 0 ? ae(re, g, _, !0) : (nt[pe - I] = b + 1, pe >= he ? he = pe : de = !0, M(
          re,
          c[pe],
          d,
          null,
          g,
          _,
          v,
          y,
          x
        ), ne++);
      }
      const Vs = de ? Yi(nt) : Ye;
      for (j = Vs.length - 1, b = se - 1; b >= 0; b--) {
        const re = I + b, pe = c[re], Bs = re + 1 < E ? c[re + 1].el : m;
        nt[b] === 0 ? M(
          null,
          pe,
          d,
          Bs,
          g,
          _,
          v,
          y,
          x
        ) : de && (j < 0 || b !== Vs[j] ? Ne(pe, d, Bs, 2) : j--);
      }
    }
  }, Ne = (l, c, d, m, g = null) => {
    const { el: _, type: v, transition: y, children: x, shapeFlag: b } = l;
    if (b & 6) {
      Ne(l.component.subTree, c, d, m);
      return;
    }
    if (b & 128) {
      l.suspense.move(c, d, m);
      return;
    }
    if (b & 64) {
      v.move(l, c, d, st);
      return;
    }
    if (v === Te) {
      n(_, c, d);
      for (let w = 0; w < x.length; w++)
        Ne(x[w], c, d, m);
      n(l.anchor, c, d);
      return;
    }
    if (v === rs) {
      W(l, c, d);
      return;
    }
    if (m !== 2 && b & 1 && y)
      if (m === 0)
        y.beforeEnter(_), n(_, c, d), ie(() => y.enter(_), g);
      else {
        const { leave: w, delayLeave: C, afterLeave: A } = y, I = () => n(_, c, d), L = () => {
          w(_, () => {
            I(), A && A();
          });
        };
        C ? C(_, I, L) : L();
      }
    else
      n(_, c, d);
  }, ae = (l, c, d, m = !1, g = !1) => {
    const {
      type: _,
      props: v,
      ref: y,
      children: x,
      dynamicChildren: b,
      shapeFlag: E,
      patchFlag: w,
      dirs: C,
      cacheIndex: A
    } = l;
    if (w === -2 && (g = !1), y != null && Ht(y, null, d, l, !0), A != null && (c.renderCache[A] = void 0), E & 256) {
      c.ctx.deactivate(l);
      return;
    }
    const I = E & 1 && C, L = !at(l);
    let j;
    if (L && (j = v && v.onVnodeBeforeUnmount) && ge(j, c, l), E & 6)
      Sr(l.component, d, m);
    else {
      if (E & 128) {
        l.suspense.unmount(d, m);
        return;
      }
      I && Le(l, null, c, "beforeUnmount"), E & 64 ? l.type.remove(
        l,
        c,
        d,
        st,
        m
      ) : b && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !b.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (_ !== Te || w > 0 && w & 64) ? tt(
        b,
        c,
        d,
        !1,
        !0
      ) : (_ === Te && w & 384 || !g && E & 16) && tt(x, c, d), m && Ls(l);
    }
    (L && (j = v && v.onVnodeUnmounted) || I) && ie(() => {
      j && ge(j, c, l), I && Le(l, null, c, "unmounted");
    }, d);
  }, Ls = (l) => {
    const { type: c, el: d, anchor: m, transition: g } = l;
    if (c === Te) {
      wr(d, m);
      return;
    }
    if (c === rs) {
      O(l);
      return;
    }
    const _ = () => {
      r(d), g && !g.persisted && g.afterLeave && g.afterLeave();
    };
    if (l.shapeFlag & 1 && g && !g.persisted) {
      const { leave: v, delayLeave: y } = g, x = () => v(d, _);
      y ? y(l.el, _, x) : x();
    } else
      _();
  }, wr = (l, c) => {
    let d;
    for (; l !== c; )
      d = S(l), r(l), l = d;
    r(c);
  }, Sr = (l, c, d) => {
    const { bum: m, scope: g, job: _, subTree: v, um: y, m: x, a: b } = l;
    Qs(x), Qs(b), m && Xt(m), g.stop(), _ && (_.flags |= 8, ae(v, l, c, d)), y && ie(y, c), ie(() => {
      l.isUnmounted = !0;
    }, c), c && c.pendingBranch && !c.isUnmounted && l.asyncDep && !l.asyncResolved && l.suspenseId === c.pendingId && (c.deps--, c.deps === 0 && c.resolve());
  }, tt = (l, c, d, m = !1, g = !1, _ = 0) => {
    for (let v = _; v < l.length; v++)
      ae(l[v], c, d, m, g);
  }, Et = (l) => {
    if (l.shapeFlag & 6)
      return Et(l.component.subTree);
    if (l.shapeFlag & 128)
      return l.suspense.next();
    const c = S(l.anchor || l.el), d = c && c[gi];
    return d ? S(d) : c;
  };
  let Yt = !1;
  const Us = (l, c, d) => {
    l == null ? c._vnode && ae(c._vnode, null, null, !0) : M(
      c._vnode || null,
      l,
      c,
      null,
      null,
      null,
      d
    ), c._vnode = l, Yt || (Yt = !0, Js(), Jn(), Yt = !1);
  }, st = {
    p: M,
    um: ae,
    m: Ne,
    r: Ls,
    mt: Gt,
    mc: Ae,
    pc: N,
    pbc: He,
    n: Et,
    o: e
  };
  return {
    render: Us,
    hydrate: void 0,
    createApp: $i(Us)
  };
}
function ss({ type: e, props: t }, s) {
  return s === "svg" && e === "foreignObject" || s === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : s;
}
function Ue({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Gi(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function ar(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (P(n) && P(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let f = r[i];
      f.shapeFlag & 1 && !f.dynamicChildren && ((f.patchFlag <= 0 || f.patchFlag === 32) && (f = r[i] = Re(r[i]), f.el = o.el), !s && f.patchFlag !== -2 && ar(o, f)), f.type === Jt && (f.el = o.el);
    }
}
function Yi(e) {
  const t = e.slice(), s = [0];
  let n, r, i, o, f;
  const u = e.length;
  for (n = 0; n < u; n++) {
    const h = e[n];
    if (h !== 0) {
      if (r = s[s.length - 1], e[r] < h) {
        t[n] = r, s.push(n);
        continue;
      }
      for (i = 0, o = s.length - 1; i < o; )
        f = i + o >> 1, e[s[f]] < h ? i = f + 1 : o = f;
      h < e[s[i]] && (i > 0 && (t[n] = s[i - 1]), s[i] = n);
    }
  }
  for (i = s.length, o = s[i - 1]; i-- > 0; )
    s[i] = o, o = t[o];
  return s;
}
function dr(e) {
  const t = e.subTree.component;
  if (t)
    return t.asyncDep && !t.asyncResolved ? t : dr(t);
}
function Qs(e) {
  if (e)
    for (let t = 0; t < e.length; t++)
      e[t].flags |= 8;
}
const zi = Symbol.for("v-scx"), Xi = () => Rt(zi);
function ns(e, t, s) {
  return hr(e, t, s);
}
function hr(e, t, s = V) {
  const { immediate: n, deep: r, flush: i, once: o } = s, f = te({}, s), u = t && n || !t && i !== "post";
  let h;
  if (xt) {
    if (i === "sync") {
      const T = Xi();
      h = T.__watcherHandles || (T.__watcherHandles = []);
    } else if (!u) {
      const T = () => {
      };
      return T.stop = xe, T.resume = xe, T.pause = xe, T;
    }
  }
  const a = k;
  f.call = (T, F, M) => ve(T, a, F, M);
  let p = !1;
  i === "post" ? f.scheduler = (T) => {
    ie(T, a && a.suspense);
  } : i !== "sync" && (p = !0, f.scheduler = (T, F) => {
    F ? T() : Ms(T);
  }), f.augmentJob = (T) => {
    t && (T.flags |= 4), p && (T.flags |= 2, a && (T.id = a.uid, T.i = a));
  };
  const S = ci(e, t, f);
  return xt && (h ? h.push(S) : u && S()), S;
}
function Zi(e, t, s) {
  const n = this.proxy, r = G(e) ? e.includes(".") ? pr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  R(t) ? i = t : (i = t.handler, s = t);
  const o = vt(this), f = hr(r, i.bind(n), s);
  return o(), f;
}
function pr(e, t) {
  const s = t.split(".");
  return () => {
    let n = e;
    for (let r = 0; r < s.length && n; r++)
      n = n[s[r]];
    return n;
  };
}
const Qi = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${Me(t)}Modifiers`] || e[`${qe(t)}Modifiers`];
function ki(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || V;
  let r = s;
  const i = t.startsWith("update:"), o = i && Qi(n, t.slice(7));
  o && (o.trim && (r = s.map((a) => G(a) ? a.trim() : a)), o.number && (r = s.map(Pr)));
  let f, u = n[f = zt(t)] || // also try camelCase event handler (#2249)
  n[f = zt(Me(t))];
  !u && i && (u = n[f = zt(qe(t))]), u && ve(
    u,
    e,
    6,
    r
  );
  const h = n[f + "Once"];
  if (h) {
    if (!e.emitted)
      e.emitted = {};
    else if (e.emitted[f])
      return;
    e.emitted[f] = !0, ve(
      h,
      e,
      6,
      r
    );
  }
}
function gr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, f = !1;
  if (!R(e)) {
    const u = (h) => {
      const a = gr(h, t, !0);
      a && (f = !0, te(o, a));
    };
    !s && t.mixins.length && t.mixins.forEach(u), e.extends && u(e.extends), e.mixins && e.mixins.forEach(u);
  }
  return !i && !f ? (q(e) && n.set(e, null), null) : (P(i) ? i.forEach((u) => o[u] = null) : te(o, i), q(e) && n.set(e, o), o);
}
function qt(e, t) {
  return !e || !Lt(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), D(e, t[0].toLowerCase() + t.slice(1)) || D(e, qe(t)) || D(e, t));
}
function ks(e) {
  const {
    type: t,
    vnode: s,
    proxy: n,
    withProxy: r,
    propsOptions: [i],
    slots: o,
    attrs: f,
    emit: u,
    render: h,
    renderCache: a,
    props: p,
    data: S,
    setupState: T,
    ctx: F,
    inheritAttrs: M
  } = e, Y = jt(e);
  let $, K;
  try {
    if (s.shapeFlag & 4) {
      const O = r || n, J = O;
      $ = me(
        h.call(
          J,
          O,
          a,
          p,
          T,
          S,
          F
        )
      ), K = f;
    } else {
      const O = t;
      $ = me(
        O.length > 1 ? O(
          p,
          { attrs: f, slots: o, emit: u }
        ) : O(
          p,
          null
        )
      ), K = t.props ? f : eo(f);
    }
  } catch (O) {
    ht.length = 0, Kt(O, e, 1), $ = We(mt);
  }
  let W = $;
  if (K && M !== !1) {
    const O = Object.keys(K), { shapeFlag: J } = W;
    O.length && J & 7 && (i && O.some(xs) && (K = to(
      K,
      i
    )), W = ke(W, K, !1, !0));
  }
  return s.dirs && (W = ke(W, null, !1, !0), W.dirs = W.dirs ? W.dirs.concat(s.dirs) : s.dirs), s.transition && Fs(W, s.transition), $ = W, jt(Y), $;
}
const eo = (e) => {
  let t;
  for (const s in e)
    (s === "class" || s === "style" || Lt(s)) && ((t || (t = {}))[s] = e[s]);
  return t;
}, to = (e, t) => {
  const s = {};
  for (const n in e)
    (!xs(n) || !(n.slice(9) in t)) && (s[n] = e[n]);
  return s;
};
function so(e, t, s) {
  const { props: n, children: r, component: i } = e, { props: o, children: f, patchFlag: u } = t, h = i.emitsOptions;
  if (t.dirs || t.transition)
    return !0;
  if (s && u >= 0) {
    if (u & 1024)
      return !0;
    if (u & 16)
      return n ? en(n, o, h) : !!o;
    if (u & 8) {
      const a = t.dynamicProps;
      for (let p = 0; p < a.length; p++) {
        const S = a[p];
        if (o[S] !== n[S] && !qt(h, S))
          return !0;
      }
    }
  } else
    return (r || f) && (!f || !f.$stable) ? !0 : n === o ? !1 : n ? o ? en(n, o, h) : !0 : !!o;
  return !1;
}
function en(e, t, s) {
  const n = Object.keys(t);
  if (n.length !== Object.keys(e).length)
    return !0;
  for (let r = 0; r < n.length; r++) {
    const i = n[r];
    if (t[i] !== e[i] && !qt(s, i))
      return !0;
  }
  return !1;
}
function no({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if (n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e)
      (e = t.vnode).el = s, t = t.parent;
    else
      break;
  }
}
const _r = (e) => e.__isSuspense;
function ro(e, t) {
  t && t.pendingBranch ? P(e) ? t.effects.push(...e) : t.effects.push(e) : hi(e);
}
const Te = Symbol.for("v-fgt"), Jt = Symbol.for("v-txt"), mt = Symbol.for("v-cmt"), rs = Symbol.for("v-stc"), ht = [];
let fe = null;
function io(e = !1) {
  ht.push(fe = e ? null : []);
}
function oo() {
  ht.pop(), fe = ht[ht.length - 1] || null;
}
let bt = 1;
function tn(e, t = !1) {
  bt += e, e < 0 && fe && t && (fe.hasOnce = !0);
}
function lo(e) {
  return e.dynamicChildren = bt > 0 ? fe || Ye : null, oo(), bt > 0 && fe && fe.push(e), e;
}
function fo(e, t, s, n, r, i) {
  return lo(
    js(
      e,
      t,
      s,
      n,
      r,
      i,
      !0
    )
  );
}
function mr(e) {
  return e ? e.__v_isVNode === !0 : !1;
}
function it(e, t) {
  return e.type === t.type && e.key === t.key;
}
const br = ({ key: e }) => e ?? null, It = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? G(e) || ee(e) || R(e) ? { i: be, r: e, k: t, f: !!s } : e : null);
function js(e, t = null, s = null, n = 0, r = null, i = e === Te ? 0 : 1, o = !1, f = !1) {
  const u = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && br(t),
    ref: t && It(t),
    scopeId: Yn,
    slotScopeIds: null,
    children: s,
    component: null,
    suspense: null,
    ssContent: null,
    ssFallback: null,
    dirs: null,
    transition: null,
    el: null,
    anchor: null,
    target: null,
    targetStart: null,
    targetAnchor: null,
    staticCount: 0,
    shapeFlag: i,
    patchFlag: n,
    dynamicProps: r,
    dynamicChildren: null,
    appContext: null,
    ctx: be
  };
  return f ? (Hs(u, s), i & 128 && e.normalize(u)) : s && (u.shapeFlag |= G(s) ? 8 : 16), bt > 0 && // avoid a block node from tracking itself
  !o && // has current parent block
  fe && // presence of a patch flag indicates this node needs patching on updates.
  // component nodes also should always be patched, because even if the
  // component doesn't need to update, it needs to persist the instance on to
  // the next vnode so that it can be properly unmounted later.
  (u.patchFlag > 0 || i & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
  // vnode should not be considered dynamic due to handler caching.
  u.patchFlag !== 32 && fe.push(u), u;
}
const We = co;
function co(e, t = null, s = null, n = 0, r = null, i = !1) {
  if ((!e || e === Pi) && (e = mt), mr(e)) {
    const f = ke(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && Hs(f, s), bt > 0 && !i && fe && (f.shapeFlag & 6 ? fe[fe.indexOf(e)] = f : fe.push(f)), f.patchFlag = -2, f;
  }
  if (vo(e) && (e = e.__vccOpts), t) {
    t = uo(t);
    let { class: f, style: u } = t;
    f && !G(f) && (t.class = Ss(f)), q(u) && (Is(u) && !P(u) && (u = te({}, u)), t.style = ws(u));
  }
  const o = G(e) ? 1 : _r(e) ? 128 : _i(e) ? 64 : q(e) ? 4 : R(e) ? 2 : 0;
  return js(
    e,
    t,
    s,
    n,
    r,
    o,
    i,
    !0
  );
}
function uo(e) {
  return e ? Is(e) || rr(e) ? te({}, e) : e : null;
}
function ke(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: f, transition: u } = e, h = t ? ho(r || {}, t) : r, a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: h,
    key: h && br(h),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? P(i) ? i.concat(It(t)) : [i, It(t)] : It(t)
    ) : i,
    scopeId: e.scopeId,
    slotScopeIds: e.slotScopeIds,
    children: f,
    target: e.target,
    targetStart: e.targetStart,
    targetAnchor: e.targetAnchor,
    staticCount: e.staticCount,
    shapeFlag: e.shapeFlag,
    // if the vnode is cloned with extra props, we can no longer assume its
    // existing patch flag to be reliable and need to add the FULL_PROPS flag.
    // note: preserve flag for fragments since they use the flag for children
    // fast paths only.
    patchFlag: t && e.type !== Te ? o === -1 ? 16 : o | 16 : o,
    dynamicProps: e.dynamicProps,
    dynamicChildren: e.dynamicChildren,
    appContext: e.appContext,
    dirs: e.dirs,
    transition: u,
    // These should technically only be non-null on mounted VNodes. However,
    // they *should* be copied for kept-alive vnodes. So we just always copy
    // them since them being non-null during a mount doesn't affect the logic as
    // they will simply be overwritten.
    component: e.component,
    suspense: e.suspense,
    ssContent: e.ssContent && ke(e.ssContent),
    ssFallback: e.ssFallback && ke(e.ssFallback),
    el: e.el,
    anchor: e.anchor,
    ctx: e.ctx,
    ce: e.ce
  };
  return u && n && Fs(
    a,
    u.clone(a)
  ), a;
}
function ao(e = " ", t = 0) {
  return We(Jt, null, e, t);
}
function me(e) {
  return e == null || typeof e == "boolean" ? We(mt) : P(e) ? We(
    Te,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : mr(e) ? Re(e) : We(Jt, null, String(e));
}
function Re(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : ke(e);
}
function Hs(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null)
    t = null;
  else if (P(t))
    s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const r = t.default;
      r && (r._c && (r._d = !1), Hs(e, r()), r._c && (r._d = !0));
      return;
    } else {
      s = 32;
      const r = t._;
      !r && !rr(t) ? t._ctx = be : r === 3 && be && (be.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else R(t) ? (t = { default: t, _ctx: be }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [ao(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function ho(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const r in n)
      if (r === "class")
        t.class !== n.class && (t.class = Ss([t.class, n.class]));
      else if (r === "style")
        t.style = ws([t.style, n.style]);
      else if (Lt(r)) {
        const i = t[r], o = n[r];
        o && i !== o && !(P(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
      } else r !== "" && (t[r] = n[r]);
  }
  return t;
}
function ge(e, t, s, n = null) {
  ve(e, t, 7, [
    s,
    n
  ]);
}
const po = tr();
let go = 0;
function _o(e, t, s) {
  const n = e.type, r = (t ? t.appContext : e.appContext) || po, i = {
    uid: go++,
    vnode: e,
    type: n,
    parent: t,
    appContext: r,
    root: null,
    // to be immediately set
    next: null,
    subTree: null,
    // will be set synchronously right after creation
    effect: null,
    update: null,
    // will be set synchronously right after creation
    job: null,
    scope: new Hr(
      !0
      /* detached */
    ),
    render: null,
    proxy: null,
    exposed: null,
    exposeProxy: null,
    withProxy: null,
    provides: t ? t.provides : Object.create(r.provides),
    ids: t ? t.ids : ["", 0, 0],
    accessCache: null,
    renderCache: [],
    // local resolved assets
    components: null,
    directives: null,
    // resolved props and emits options
    propsOptions: or(n, r),
    emitsOptions: gr(n, r),
    // emit
    emit: null,
    // to be set immediately
    emitted: null,
    // props default value
    propsDefaults: V,
    // inheritAttrs
    inheritAttrs: n.inheritAttrs,
    // state
    ctx: V,
    data: V,
    props: V,
    attrs: V,
    slots: V,
    refs: V,
    setupState: V,
    setupContext: null,
    // suspense related
    suspense: s,
    suspenseId: s ? s.pendingId : 0,
    asyncDep: null,
    asyncResolved: !1,
    // lifecycle hooks
    // not using enums here because it results in computed properties
    isMounted: !1,
    isUnmounted: !1,
    isDeactivated: !1,
    bc: null,
    c: null,
    bm: null,
    m: null,
    bu: null,
    u: null,
    um: null,
    bum: null,
    da: null,
    a: null,
    rtg: null,
    rtc: null,
    ec: null,
    sp: null
  };
  return i.ctx = { _: i }, i.root = t ? t.root : i, i.emit = ki.bind(null, i), e.ce && e.ce(i), i;
}
let k = null, Nt, _s;
{
  const e = Bt(), t = (s, n) => {
    let r;
    return (r = e[s]) || (r = e[s] = []), r.push(n), (i) => {
      r.length > 1 ? r.forEach((o) => o(i)) : r[0](i);
    };
  };
  Nt = t(
    "__VUE_INSTANCE_SETTERS__",
    (s) => k = s
  ), _s = t(
    "__VUE_SSR_SETTERS__",
    (s) => xt = s
  );
}
const vt = (e) => {
  const t = k;
  return Nt(e), e.scope.on(), () => {
    e.scope.off(), Nt(t);
  };
}, sn = () => {
  k && k.scope.off(), Nt(null);
};
function xr(e) {
  return e.vnode.shapeFlag & 4;
}
let xt = !1;
function mo(e, t = !1, s = !1) {
  t && _s(t);
  const { props: n, children: r } = e.vnode, i = xr(e);
  Li(e, n, i, t), Ki(e, r, s);
  const o = i ? bo(e, t) : void 0;
  return t && _s(!1), o;
}
function bo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, Ri);
  const { setup: n } = s;
  if (n) {
    De();
    const r = e.setupContext = n.length > 1 ? yo(e) : null, i = vt(e), o = yt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), f = bn(o);
    if (je(), i(), (f || e.sp) && !at(e) && zn(e), f) {
      if (o.then(sn, sn), t)
        return o.then((u) => {
          nn(e, u);
        }).catch((u) => {
          Kt(u, e, 0);
        });
      e.asyncDep = o;
    } else
      nn(e, o);
  } else
    yr(e);
}
function nn(e, t, s) {
  R(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : q(t) && (e.setupState = Kn(t)), yr(e);
}
function yr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || xe);
  {
    const r = vt(e);
    De();
    try {
      Ii(e);
    } finally {
      je(), r();
    }
  }
}
const xo = {
  get(e, t) {
    return z(e, "get", ""), e[t];
  }
};
function yo(e) {
  const t = (s) => {
    e.exposed = s || {};
  };
  return {
    attrs: new Proxy(e.attrs, xo),
    slots: e.slots,
    emit: e.emit,
    expose: t
  };
}
function $s(e) {
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(Kn(ni(e.exposed)), {
    get(t, s) {
      if (s in t)
        return t[s];
      if (s in dt)
        return dt[s](e);
    },
    has(t, s) {
      return s in t || s in dt;
    }
  })) : e.proxy;
}
function vo(e) {
  return R(e) && "__vccOpts" in e;
}
const wo = (e, t) => li(e, t, xt), So = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let ms;
const rn = typeof window < "u" && window.trustedTypes;
if (rn)
  try {
    ms = /* @__PURE__ */ rn.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const vr = ms ? (e) => ms.createHTML(e) : (e) => e, To = "http://www.w3.org/2000/svg", Co = "http://www.w3.org/1998/Math/MathML", Se = typeof document < "u" ? document : null, on = Se && /* @__PURE__ */ Se.createElement("template"), Eo = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? Se.createElementNS(To, e) : t === "mathml" ? Se.createElementNS(Co, e) : s ? Se.createElement(e, { is: s }) : Se.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => Se.createTextNode(e),
  createComment: (e) => Se.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => Se.querySelector(e),
  setScopeId(e, t) {
    e.setAttribute(t, "");
  },
  // __UNSAFE__
  // Reason: innerHTML.
  // Static content here can only come from compiled templates.
  // As long as the user only uses trusted templates, this is safe.
  insertStaticContent(e, t, s, n, r, i) {
    const o = s ? s.previousSibling : t.lastChild;
    if (r && (r === i || r.nextSibling))
      for (; t.insertBefore(r.cloneNode(!0), s), !(r === i || !(r = r.nextSibling)); )
        ;
    else {
      on.innerHTML = vr(
        n === "svg" ? `<svg>${e}</svg>` : n === "mathml" ? `<math>${e}</math>` : e
      );
      const f = on.content;
      if (n === "svg" || n === "mathml") {
        const u = f.firstChild;
        for (; u.firstChild; )
          f.appendChild(u.firstChild);
        f.removeChild(u);
      }
      t.insertBefore(f, s);
    }
    return [
      // first
      o ? o.nextSibling : t.firstChild,
      // last
      s ? s.previousSibling : t.lastChild
    ];
  }
}, Oo = Symbol("_vtc");
function Ao(e, t, s) {
  const n = e[Oo];
  n && (t = (t ? [t, ...n] : [...n]).join(" ")), t == null ? e.removeAttribute("class") : s ? e.setAttribute("class", t) : e.className = t;
}
const ln = Symbol("_vod"), Po = Symbol("_vsh"), Ro = Symbol(""), Io = /(^|;)\s*display\s*:/;
function Mo(e, t, s) {
  const n = e.style, r = G(s);
  let i = !1;
  if (s && !r) {
    if (t)
      if (G(t))
        for (const o of t.split(";")) {
          const f = o.slice(0, o.indexOf(":")).trim();
          s[f] == null && Mt(n, f, "");
        }
      else
        for (const o in t)
          s[o] == null && Mt(n, o, "");
    for (const o in s)
      o === "display" && (i = !0), Mt(n, o, s[o]);
  } else if (r) {
    if (t !== s) {
      const o = n[Ro];
      o && (s += ";" + o), n.cssText = s, i = Io.test(s);
    }
  } else t && e.removeAttribute("style");
  ln in e && (e[ln] = i ? n.display : "", e[Po] && (n.display = "none"));
}
const fn = /\s*!important$/;
function Mt(e, t, s) {
  if (P(s))
    s.forEach((n) => Mt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = Fo(e, t);
    fn.test(s) ? e.setProperty(
      qe(n),
      s.replace(fn, ""),
      "important"
    ) : e[n] = s;
  }
}
const cn = ["Webkit", "Moz", "ms"], is = {};
function Fo(e, t) {
  const s = is[t];
  if (s)
    return s;
  let n = Me(t);
  if (n !== "filter" && n in e)
    return is[t] = n;
  n = vn(n);
  for (let r = 0; r < cn.length; r++) {
    const i = cn[r] + n;
    if (i in e)
      return is[t] = i;
  }
  return t;
}
const un = "http://www.w3.org/1999/xlink";
function an(e, t, s, n, r, i = jr(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(un, t.slice(6, t.length)) : e.setAttributeNS(un, t, s) : s == null || i && !Sn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Fe(s) ? String(s) : s
  );
}
function dn(e, t, s, n, r) {
  if (t === "innerHTML" || t === "textContent") {
    s != null && (e[t] = t === "innerHTML" ? vr(s) : s);
    return;
  }
  const i = e.tagName;
  if (t === "value" && i !== "PROGRESS" && // custom elements may use _value internally
  !i.includes("-")) {
    const f = i === "OPTION" ? e.getAttribute("value") || "" : e.value, u = s == null ? (
      // #11647: value should be set as empty string for null and undefined,
      // but <input type="checkbox"> should be set as 'on'.
      e.type === "checkbox" ? "on" : ""
    ) : String(s);
    (f !== u || !("_value" in e)) && (e.value = u), s == null && e.removeAttribute(t), e._value = s;
    return;
  }
  let o = !1;
  if (s === "" || s == null) {
    const f = typeof e[t];
    f === "boolean" ? s = Sn(s) : s == null && f === "string" ? (s = "", o = !0) : f === "number" && (s = 0, o = !0);
  }
  try {
    e[t] = s;
  } catch {
  }
  o && e.removeAttribute(r || t);
}
function Do(e, t, s, n) {
  e.addEventListener(t, s, n);
}
function jo(e, t, s, n) {
  e.removeEventListener(t, s, n);
}
const hn = Symbol("_vei");
function Ho(e, t, s, n, r = null) {
  const i = e[hn] || (e[hn] = {}), o = i[t];
  if (n && o)
    o.value = n;
  else {
    const [f, u] = $o(t);
    if (n) {
      const h = i[t] = Uo(
        n,
        r
      );
      Do(e, f, h, u);
    } else o && (jo(e, f, o, u), i[t] = void 0);
  }
}
const pn = /(?:Once|Passive|Capture)$/;
function $o(e) {
  let t;
  if (pn.test(e)) {
    t = {};
    let n;
    for (; n = e.match(pn); )
      e = e.slice(0, e.length - n[0].length), t[n[0].toLowerCase()] = !0;
  }
  return [e[2] === ":" ? e.slice(3) : qe(e.slice(2)), t];
}
let os = 0;
const No = /* @__PURE__ */ Promise.resolve(), Lo = () => os || (No.then(() => os = 0), os = Date.now());
function Uo(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    ve(
      Vo(n, s.value),
      t,
      5,
      [n]
    );
  };
  return s.value = e, s.attached = Lo(), s;
}
function Vo(e, t) {
  if (P(t)) {
    const s = e.stopImmediatePropagation;
    return e.stopImmediatePropagation = () => {
      s.call(e), e._stopped = !0;
    }, t.map(
      (n) => (r) => !r._stopped && n && n(r)
    );
  } else
    return t;
}
const gn = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // lowercase letter
e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, Bo = (e, t, s, n, r, i) => {
  const o = r === "svg";
  t === "class" ? Ao(e, n, o) : t === "style" ? Mo(e, s, n) : Lt(t) ? xs(t) || Ho(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : Ko(e, t, n, o)) ? (dn(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && an(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !G(n)) ? dn(e, Me(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), an(e, t, n, o));
};
function Ko(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && gn(t) && R(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return gn(t) && G(s) ? !1 : t in e;
}
const Wo = /* @__PURE__ */ te({ patchProp: Bo }, Eo);
let _n;
function qo() {
  return _n || (_n = qi(Wo));
}
const Jo = (...e) => {
  const t = qo().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Yo(n);
    if (!r) return;
    const i = t._component;
    !R(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
    const o = s(r, !1, Go(r));
    return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), o;
  }, t;
};
function Go(e) {
  if (e instanceof SVGElement)
    return "svg";
  if (typeof MathMLElement == "function" && e instanceof MathMLElement)
    return "mathml";
}
function Yo(e) {
  return G(e) ? document.querySelector(e) : e;
}
const zo = (e, t) => {
  const s = e.__vccOpts || e;
  for (const [n, r] of t)
    s[n] = r;
  return s;
}, Xo = {
  name: "dm-json-form3",
  components: {},
  props: {
    options: {
      type: Object
    },
    schema: {
      type: Object
    },
    data: {
      type: Object
    },
    enabled: {
      type: Boolean,
      default: !0
    },
    title: {
      type: String,
      default: ""
    }
  },
  async mounted() {
    await import("https://esm.sh/@json-editor/json-editor@latest");
    const e = { theme: "bootstrap4", iconlib: "spectre", remove_button_labels: !0, ajax: !0, ajax_cache_responses: !1, disable_collapse: !1, disable_edit_json: !0, disable_properties: !1, use_default_values: !0, required_by_default: !1, display_required_only: !0, show_opt_in: !1, show_errors: "always", disable_array_reorder: !1, disable_array_delete_all_rows: !1, disable_array_delete_last_row: !1, keep_oneof_values: !1, no_additional_properties: !0, case_sensitive_property_search: !1, ...this.options };
    console.warn("Options: ", e);
    var t = new JSONEditor(this.$el, e);
    console.warn("Editor: ", this.editor), t.on("ready", () => {
      this.enabled === !1 && t.disable();
    }), t.on("change", () => {
      this.$emit("change", t.getValue());
    });
  },
  /*watch: {
    data(value) { this.editor.setValue(value) }
  },*/
  emits: ["onChange"]
}, Zo = {
  ref: "jsoneditor",
  id: "jsoneditor",
  class: "bootstrap-wrapper"
};
function Qo(e, t, s, n, r, i) {
  return io(), fo("div", Zo, [
    js("h2", null, Cn(s.title), 1)
  ], 512);
}
const ko = /* @__PURE__ */ zo(Xo, [["render", Qo]]);
function tl({ model: e, el: t }) {
  const s = document.createElement("div");
  s.setAttribute("id", "jsoneditor-container"), t.append(s), console.log("Create App");
  let n = e.get("options");
  n = n || {
    theme: "bootstrap4",
    iconlib: "spectre",
    schema: {
      title: "Editor Test",
      required: ["test"],
      properties: { test: { type: "string" } }
    }
    //   startval: this.data
  }, Jo(ko, {
    options: n,
    onChange: (i) => {
      console.log("CHANGE", i), e.set("value", i), e.save_changes();
    }
  }).mount(t);
}
export {
  tl as render
};
