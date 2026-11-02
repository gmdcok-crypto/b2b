(function () {
  const data = window.SAMPLE;
  const TITLES = { orders: "발주", prices: "단가", items: "품목", vendors: "협력사", audit: "이력" };
  const ITEM_GROUPS = ["원자재", "기자재", "가공품", "포장", "보전", "사출", "소모품"];
  const ITEM_UNITS = ["EA", "M", "KG", "BOX"];
  let itemSeq = 1;
  let vendorSeq = 1;
  const state = {
    module: "orders",
    selectedId: data.orders[0].id,
    sortKey: "date",
    sortDir: "desc",
    split: 42,
    message: "",
    api: "API 확인 중",
    timer: 0,
    filters: {}
  };

  const $ = (id) => document.getElementById(id);
  const today = new Date();
  $("today").textContent = formatDate(today);
  $("today").setAttribute("datetime", formatDate(today));

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => openModule(button.dataset.module));
  });

  openModule("orders");
  checkApi();

  function openModule(name) {
    state.module = name;
    state.message = "";
    state.sortKey = name === "orders" ? "date" : name === "audit" ? "at" : "code";
    state.sortDir = name === "prices" || name === "items" || name === "vendors" ? "asc" : "desc";
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.module === name);
    });
    $("crumb").textContent = TITLES[name];
    renderCriteria();
    state.selectedId = firstId(filtered());
    renderCommand();
    renderWorkspace();
    renderStatus();
  }

  function renderCommand() {
    const bar = $("command");
    bar.replaceChildren();
    const spec = commands();
    spec.forEach((item, index) => {
      if (item === "|") {
        bar.append(el("span", { class: "sep-v" }));
        return;
      }
      const enabled = item.enable ? item.enable() : true;
      bar.append(el("button", {
        type: "button",
        class: "btn" + (item.kind ? " " + item.kind : ""),
        disabled: enabled ? null : "disabled",
        onclick: () => {
          if (item.enable && !item.enable()) return;
          item.run();
          renderCommand();
          renderStatus();
        }
      }, item.label));
      void index;
    });
  }

  function commands() {
    if (state.module === "orders") {
      const order = selectedOrder();
      return [
        { label: "조회", kind: "primary", run: () => toast(countText(filtered().length)) },
        "|",
        { label: "신규", run: newOrder },
        { label: "저장", enable: () => order && order.status === "작성", run: () => toast("화면의 작성 내용을 유지했습니다. 서버 저장은 아직 연결되지 않았습니다.") },
        "|",
        { label: "확정", enable: () => order && order.status === "작성", run: confirmOrder },
        { label: "발주취소", kind: "danger", enable: () => order && order.status === "확정", run: cancelOrder },
        "|",
        { label: "인쇄", enable: () => !!order, run: printCurrent }
      ];
    }
    if (state.module === "prices") {
      const price = selectedPrice();
      return [
        { label: "조회", kind: "primary", run: () => toast(countText(filtered().length)) },
        "|",
        { label: "신규", run: newPrice },
        { label: "저장", enable: () => price && price.draft, run: savePrice },
        "|",
        { label: "변경요청", enable: () => price && price.status === "적용중", run: requestPrice },
        { label: "승인", enable: () => price && price.status === "승인대기", run: () => decidePrice("승인") },
        { label: "반려", kind: "danger", enable: () => price && price.status === "승인대기", run: () => decidePrice("반려") },
        "|",
        { label: "인쇄", run: printCurrent }
      ];
    }
    if (state.module === "items") {
      const item = selectedItem();
      const inUse = !item || item.use !== "중지";
      return [
        { label: "조회", kind: "primary", run: () => toast(countText(filtered().length)) },
        "|",
        { label: "신규", run: newItem },
        { label: "저장", enable: () => !!item, run: saveItem },
        "|",
        {
          label: inUse ? "사용중지" : "사용재개",
          kind: inUse ? "danger" : "",
          enable: () => item && !item.draft,
          run: () => setItemUse(inUse ? "중지" : "사용")
        },
        "|",
        { label: "인쇄", enable: () => !!item && !item.draft, run: printCurrent }
      ];
    }
    if (state.module === "vendors") {
      const vendor = selectedVendor();
      const inUse = !vendor || vendor.use !== "중지";
      return [
        { label: "조회", kind: "primary", run: () => toast(countText(filtered().length)) },
        "|",
        { label: "신규", run: newVendor },
        { label: "저장", enable: () => !!vendor, run: saveVendor },
        "|",
        {
          label: inUse ? "사용중지" : "사용재개",
          kind: inUse ? "danger" : "",
          enable: () => vendor && !vendor.draft,
          run: () => setVendorUse(inUse ? "중지" : "사용")
        },
        "|",
        { label: "인쇄", enable: () => !!vendor && !vendor.draft, run: printCurrent }
      ];
    }
    return [
      { label: "조회", kind: "primary", run: () => toast(countText(filtered().length)) },
      "|",
      { label: "인쇄", run: printCurrent }
    ];
  }

  function renderCriteria() {
    const box = $("criteria");
    box.replaceChildren();
    if (state.module === "orders") {
      box.append(
        field("발주일", dateInput("from", "2026-01-01"), el("span", { class: "tilde" }, "~"), dateInput("to", "2026-12-31")),
        field("상태", select("status", ["전체", "작성", "확정", "취소"], "전체")),
        field("협력사", textInput("vendor", "vendor", "")),
        field("검색", searchInput("q", "문서번호, 품목"))
      );
    } else if (state.module === "prices") {
      box.append(
        field("상태", select("status", ["전체", "작성", "적용중", "승인대기", "종료"], "전체")),
        field("협력사", textInput("vendor", "vendor", "")),
        field("검색", searchInput("q", "품목코드, 품목명"))
      );
    } else if (state.module === "items") {
      box.append(
        field("사용", select("use", ["전체", "사용", "중지"], "전체")),
        field("분류", select("group", ["전체", "원자재", "기자재", "가공품", "포장", "보전", "사출", "소모품"], "전체")),
        field("검색", searchInput("q", "품목코드, 품목명, 규격"))
      );
    } else if (state.module === "vendors") {
      box.append(
        field("사용", select("use", ["전체", "사용", "중지"], "전체")),
        field("검색", searchInput("q", "협력사코드, 협력사명, 담당자"))
      );
    } else {
      box.append(
        field("작업", select("action", ["전체", "작성", "확정", "취소", "변경요청", "승인", "반려", "종료", "등록", "수정", "사용중지", "사용재개"], "전체")),
        field("검색", searchInput("q", "대상, 사용자, 내용"))
      );
    }
    state.filters = readFilters();
    box.oninput = onFilter;
    box.onchange = onFilter;
  }

  function onFilter() {
    state.filters = readFilters();
    const rows = filtered();
    if (!rows.some((row) => rowId(row) === state.selectedId)) state.selectedId = firstId(rows);
    paintList();
    paintDetail();
    renderCommand();
    renderStatus();
  }

  function readFilters() {
    const filters = {};
    $("criteria").querySelectorAll("[data-filter]").forEach((node) => {
      filters[node.dataset.filter] = node.value.trim();
    });
    return filters;
  }

  function renderWorkspace() {
    const root = $("composite");
    root.replaceChildren();
    if (state.module === "audit") {
      root.append(pane("audit-pane", "변경 이력", "audit-cap"));
      paintList();
      paintTab();
      return;
    }
    const list = pane("list-pane", listCaption(), "list-cap");
    const splitter = el("div", { class: "splitter", role: "separator", "aria-orientation": "vertical", "aria-label": "목록 너비" });
    const detail = pane("detail-pane", detailCaption(), "detail-cap");
    list.style.flexBasis = state.split + "%";
    root.append(list, splitter, detail);
    wireSplitter(splitter, list);
    paintList();
    paintDetail();
    paintTab();
  }

  function paintList() {
    const host = $("composite").querySelector(".list-pane .grid-scroll, .audit-pane .grid-scroll");
    if (!host) return;
    const rows = sortRows(filtered());
    const columns = listColumns();
    host.replaceChildren(gridTable(columns, rows, true));
    const meta = document.querySelector(".list-pane .cap-meta, .audit-pane .cap-meta");
    if (meta) meta.textContent = rows.length + "건";
    const body = host.querySelector("tbody");
    body.addEventListener("click", (event) => {
      const tr = event.target.closest("tr[data-id]");
      if (!tr) return;
      choose(tr.dataset.id, false);
      host.focus();
    });
    host.onkeydown = (event) => {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      if (event.target.closest("input, select")) return;
      event.preventDefault();
      move(event.key === "ArrowDown" ? 1 : -1);
    };
    paintTab();
  }

  function paintDetail() {
    const paneNode = $("composite").querySelector(".detail-pane");
    if (!paneNode) return;
    const form = paneNode.querySelector(".form");
    const lines = paneNode.querySelector(".line-scroll");
    const record = selectedRecord();
    form.replaceChildren();
    if (!record) {
      lines.replaceChildren(el("div", { class: "empty" }, "선택된 자료가 없습니다."));
      return;
    }
    headerFields(record).forEach((row) => {
      row.forEach((field) => {
        form.append(el("div", { class: "lab" }, field.label));
        const editable = field.edit && canEdit(record);
        const wrap = el("div", { class: "val" + (field.span ? " span" : "") + (editable ? " edit" : "") });
        const input = field.options && editable
          ? fieldSelect(record, field)
          : el("input", fieldInputAttrs(record, field, editable));
        if (editable && !field.options) {
          input.addEventListener("input", () => {
            record[field.key] = input.value;
            syncListRow(record);
            paintTab();
            renderStatus();
          });
        }
        wrap.append(input);
        form.append(wrap);
      });
    });
    const lineRows = lineRecords(record);
    lines.replaceChildren(gridTable(lineColumns(record), lineRows, false));
    lines.querySelectorAll(".cell-input").forEach((input) => {
      input.addEventListener("input", () => {
        const line = lineRows[Number(input.dataset.index)];
        const key = input.dataset.key;
        line[key] = key === "qty" || key === "price" || key === "request" ? Number(input.value || 0) : input.value;
        if (state.module === "orders") {
          const amountCell = input.closest("tr").querySelector("[data-amount]");
          if (amountCell) amountCell.textContent = money(lineAmount(line));
          updateOrderFoot(lines, record);
          syncListRow(record);
        }
        renderStatus();
      });
    });
    const meta = paneNode.querySelector(".detail-lines .cap-meta");
    if (meta) meta.textContent = state.module === "orders" ? "부가세 별도" : lineRows.length + "건";
  }

  function choose(id, repaintList) {
    state.selectedId = id;
    if (repaintList) paintList();
    else markSelected();
    paintDetail();
    renderCommand();
    paintTab();
    renderStatus();
    const selected = $("composite").querySelector("tr.is-selected");
    if (selected) selected.scrollIntoView({ block: "nearest" });
  }

  function move(step) {
    const rows = sortRows(filtered());
    const index = rows.findIndex((row) => rowId(row) === state.selectedId);
    const next = rows[index + step];
    if (!next) return;
    choose(rowId(next), false);
  }

  function markSelected() {
    $("composite").querySelectorAll("tbody tr[data-id]").forEach((tr) => {
      tr.classList.toggle("is-selected", tr.dataset.id === state.selectedId);
      tr.setAttribute("aria-selected", tr.dataset.id === state.selectedId ? "true" : "false");
    });
  }

  function gridTable(columns, rows, selectable) {
    const table = el("table", { class: "grid" });
    const colgroup = el("colgroup");
    columns.forEach((column) => colgroup.append(el("col", column.width ? { style: "width:" + column.width } : {})));
    const head = el("thead");
    const headRow = el("tr");
    columns.forEach((column) => {
      const sorted = state.sortKey === column.key;
      const th = el("th", {
        class: column.align === "num" ? "num" : "",
        "aria-sort": sorted ? (state.sortDir === "asc" ? "ascending" : "descending") : "none"
      });
      if (column.sort === false || !selectable) {
        th.textContent = column.label;
      } else {
        th.append(el("button", {
          type: "button",
          onclick: () => {
            if (state.sortKey === column.key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
            else {
              state.sortKey = column.key;
              state.sortDir = "asc";
            }
            paintList();
          }
        }, column.label, sorted ? el("span", { class: "mark-sort" }, state.sortDir === "asc" ? "▲" : "▼") : null));
      }
      if (column.align === "num" && !selectable) th.classList.add("num");
      headRow.append(th);
    });
    head.append(headRow);
    const body = el("tbody");
    if (!rows.length) {
      body.append(el("tr", {}, el("td", { class: "empty", colspan: String(columns.length) }, "조회 결과가 없습니다.")));
    }
    rows.forEach((row, index) => {
      const id = selectable ? rowId(row) : "";
      const tr = el("tr", selectable ? { "data-id": id, "aria-selected": id === state.selectedId ? "true" : "false" } : {});
      if (selectable && id === state.selectedId) tr.classList.add("is-selected");
      columns.forEach((column) => {
        const td = el("td", { class: column.align === "num" ? "num" : "" });
        const value = column.render ? column.render(row, index) : row[column.key];
        if (value && value.nodeType) td.append(value);
        else td.textContent = value == null || value === "" ? "" : String(value);
        tr.append(td);
      });
      body.append(tr);
    });
    table.append(colgroup, head, body);
    if (!selectable && state.module === "orders") {
      const record = selectedOrder();
      const foot = el("tfoot");
      const tr = el("tr");
      columns.forEach((column, index) => {
        const td = el("td", { class: column.align === "num" ? "num" : "", "data-foot": column.key || "" });
        if (index === 1) td.textContent = "합계";
        if (column.key === "qty") td.textContent = qty(record.lines.reduce((sum, line) => sum + Number(line.qty || 0), 0));
        if (column.key === "amount") td.textContent = money(orderAmount(record));
        tr.append(td);
      });
      foot.append(tr);
      table.append(foot);
    }
    return table;
  }

  function listColumns() {
    if (state.module === "orders") {
      return [
        { key: "id", label: "문서번호", width: "118px" },
        { key: "date", label: "발주일", width: "92px" },
        { key: "vendor", label: "협력사" },
        { key: "status", label: "상태", width: "68px", render: (row) => stateNode(row.status) },
        { key: "amount", label: "공급가액", width: "108px", align: "num", sort: true, render: (row) => money(orderAmount(row)) }
      ];
    }
    if (state.module === "prices") {
      return [
        { key: "code", label: "품목코드", width: "124px" },
        { key: "name", label: "품목명" },
        { key: "vendor", label: "협력사", width: "132px" },
        { key: "price", label: "현재단가", width: "96px", align: "num", render: (row) => money(row.price) },
        { key: "from", label: "적용시작", width: "96px" },
        { key: "status", label: "상태", width: "84px", render: (row) => stateNode(row.status) }
      ];
    }
    if (state.module === "items") {
      return [
        { key: "code", label: "품목코드", width: "124px" },
        { key: "name", label: "품목명" },
        { key: "spec", label: "규격", width: "140px" },
        { key: "unit", label: "단위", width: "56px" },
        { key: "group", label: "분류", width: "72px" },
        { key: "use", label: "사용", width: "64px", render: (row) => stateNode(row.use) }
      ];
    }
    if (state.module === "vendors") {
      return [
        { key: "code", label: "협력사코드", width: "108px" },
        { key: "name", label: "협력사명" },
        { key: "bizNo", label: "사업자번호", width: "120px" },
        { key: "contact", label: "담당자", width: "88px" },
        { key: "phone", label: "전화", width: "120px" },
        { key: "use", label: "사용", width: "64px", render: (row) => stateNode(row.use) }
      ];
    }
    return [
      { key: "at", label: "일시", width: "140px" },
      { key: "user", label: "사용자", width: "120px" },
      { key: "action", label: "작업", width: "84px", render: (row) => stateNode(row.action) },
      { key: "target", label: "대상", width: "150px" },
      { key: "before", label: "이전", width: "100px" },
      { key: "after", label: "이후", width: "100px" },
      { key: "note", label: "내용" }
    ];
  }

  function lineColumns(record) {
    if (state.module === "orders") {
      const edit = record.status === "작성";
      return [
        { label: "No", width: "36px", align: "num", render: (_row, index) => String(index + 1) },
        { label: "품목코드", width: "108px", render: (row, index) => lineCell(row, index, "code", edit) },
        { label: "품목명", render: (row, index) => lineCell(row, index, "name", edit) },
        { label: "규격", width: "96px", render: (row, index) => lineCell(row, index, "spec", edit) },
        { label: "단위", width: "42px", render: (row, index) => lineCell(row, index, "unit", edit) },
        { key: "qty", label: "수량", width: "64px", align: "num", render: (row, index) => lineCell(row, index, "qty", edit, true) },
        { key: "price", label: "단가", width: "76px", align: "num", render: (row, index) => lineCell(row, index, "price", edit, true) },
        { key: "amount", label: "공급가액", width: "96px", align: "num", render: (row) => el("span", { "data-amount": "1" }, money(lineAmount(row))) },
        { label: "납기", width: "92px", render: (row, index) => lineCell(row, index, "due", edit) }
      ];
    }
    if (state.module === "prices") {
      return [
        { label: "일자", width: "110px", render: (row) => row.date },
        { label: "구분", width: "84px", render: (row) => stateNode(row.type) },
        { label: "이전단가", width: "100px", align: "num", render: (row) => row.before === "" ? "" : money(row.before) },
        { label: "변경단가", width: "100px", align: "num", render: (row) => money(row.after) },
        { label: "처리자", width: "120px", render: (row) => row.by },
        { label: "내용", render: (row) => row.note }
      ];
    }
    if (state.module === "vendors") {
      return [
        { label: "품목코드", width: "124px", render: (row) => row.code },
        { label: "품목명", render: (row) => row.name },
        { label: "계약단가", width: "100px", align: "num", render: (row) => money(row.price) },
        { label: "적용시작", width: "110px", render: (row) => row.from },
        { label: "상태", width: "84px", render: (row) => stateNode(row.status) }
      ];
    }
    return [
      { label: "협력사", render: (row) => row.vendor },
      { label: "계약단가", width: "100px", align: "num", render: (row) => money(row.price) },
      { label: "적용시작", width: "110px", render: (row) => row.from },
      { label: "적용종료", width: "110px", render: (row) => row.to || "—" },
      { label: "상태", width: "84px", render: (row) => stateNode(row.status) }
    ];
  }

  function headerFields(record) {
    if (state.module === "orders") {
      return [
        [
          { label: "문서번호", key: "id" },
          { label: "상태", key: "status" },
          { label: "발주일", key: "date", edit: true },
          { label: "납기일", key: "due", edit: true }
        ],
        [
          { label: "협력사", key: "vendor", edit: true, options: vendorNames(record.vendor), allowEmpty: true },
          { label: "담당", key: "buyer", edit: true },
          { label: "통화", key: "currency" },
          { label: "부가세", key: "vat" }
        ],
        [{ label: "비고", key: "note", edit: true, span: true }]
      ];
    }
    if (state.module === "prices") {
      const drafting = !!record.draft;
      const rows = [
        [
          { label: "단가번호", key: "id" },
          { label: "상태", key: "status" },
          { label: "적용시작", key: "from", edit: drafting, date: true },
          { label: "적용종료", key: "to", edit: drafting, date: true }
        ],
        [
          { label: "품목코드", key: "code", edit: drafting, options: priceItemCodes(record), allowEmpty: true, after: refreshPriceItem },
          { label: "품목명", key: "name" },
          { label: "규격", key: "spec" },
          { label: "단위", key: "unit" }
        ],
        [{ label: "협력사", key: "vendor", edit: drafting, options: vendorNames(record.vendor), allowEmpty: true, span: true }],
        [{ label: "계약단가", key: "price", edit: drafting, money: true, span: true }],
        [{ label: "비고", key: "note", edit: drafting, span: true }]
      ];
      if (!drafting) rows.push([{ label: "요청단가", key: "request", edit: record.status === "적용중", money: true, span: true }]);
      return rows;
    }
    if (state.module === "vendors") {
      return [
        [
          { label: "협력사코드", key: "code", edit: !!record.draft },
          { label: "사용", key: "use" },
          { label: "사업자번호", key: "bizNo", edit: true },
          { label: "전화", key: "phone", edit: true }
        ],
        [{ label: "협력사명", key: "name", edit: true, span: true }],
        [{ label: "담당자", key: "contact", edit: true, span: true }],
        [{ label: "이메일", key: "email", edit: true, span: true }]
      ];
    }
    const units = ITEM_UNITS.slice();
    const groups = ITEM_GROUPS.slice();
    if (record.unit && !units.includes(record.unit)) units.unshift(record.unit);
    if (record.group && !groups.includes(record.group)) groups.unshift(record.group);
    return [
      [
        { label: "품목코드", key: "code", edit: !!record.draft },
        { label: "사용", key: "use" },
        { label: "단위", key: "unit", edit: true, options: units },
        { label: "분류", key: "group", edit: true, options: groups }
      ],
      [{ label: "품목명", key: "name", edit: true, span: true }],
      [{ label: "규격", key: "spec", edit: true, span: true }]
    ];
  }

  function newPrice() {
    const current = selectedPrice();
    if (current && current.draft && !current.code) {
      const input = $("composite").querySelector('[data-field="code"]');
      if (input) input.focus();
      return;
    }
    const price = {
      id: nextPriceId(),
      code: "",
      name: "",
      spec: "",
      unit: "",
      vendor: "",
      price: "",
      request: "",
      from: formatDate(new Date()),
      to: "",
      note: "",
      status: "작성",
      draft: true,
      history: []
    };
    data.prices.unshift(price);
    state.filters = {};
    renderCriteria();
    state.selectedId = price.id;
    renderWorkspace();
    toast("계약단가 등록을 열었습니다. 품목과 단가를 입력한 뒤 저장하세요.");
    const input = $("composite").querySelector('[data-field="code"]');
    if (input) input.focus();
  }

  function savePrice() {
    const price = selectedPrice();
    if (!price || !price.draft) return;
    const item = data.items.find((row) => row.code === price.code);
    if (!price.code || !item) {
      toast("품목을 선택하세요.");
      return;
    }
    if (item.use !== "사용") {
      toast("사용 중인 품목만 계약단가를 등록할 수 있습니다.");
      return;
    }
    const vendor = String(price.vendor || "").trim();
    const supplier = data.vendors.find((row) => row.name === vendor && row.use === "사용" && !row.draft);
    if (!vendor || !supplier) {
      toast("사용 중인 협력사를 선택하세요.");
      return;
    }
    const amount = String(price.price == null ? "" : price.price).replace(/,/g, "").trim();
    if (!amount) {
      toast("계약단가를 입력하세요.");
      return;
    }
    if (!/^[0-9]+$/.test(amount) || Number(amount) <= 0) {
      toast("계약단가는 1원 이상의 정수로 입력하세요.");
      return;
    }
    if (!isIsoDate(price.from)) {
      toast("적용시작일을 입력하세요.");
      return;
    }
    if (price.to && !isIsoDate(price.to)) {
      toast("적용종료일을 입력하세요.");
      return;
    }
    if (price.to && price.to < price.from) {
      toast("적용종료일은 적용시작일 이후로 입력하세요.");
      return;
    }
    applyPriceItem(price);
    price.vendor = vendor;
    price.price = Number(amount);
    price.note = String(price.note || "").trim();
    price.request = "";
    price.status = "적용중";
    price.draft = false;
    price.history.unshift({
      date: formatDate(new Date()),
      type: "등록",
      before: "",
      after: price.price,
      by: "김구매",
      note: price.note
    });
    pushAudit("등록", price.code, "", money(price.price), price.vendor);
    paintList();
    paintDetail();
    toast("계약단가를 등록했습니다. 서버 저장은 아직 연결되지 않았습니다.");
  }

  function applyPriceItem(record) {
    const item = data.items.find((row) => row.code === record.code);
    record.name = item ? item.name : "";
    record.spec = item ? item.spec : "";
    record.unit = item ? item.unit : "";
  }

  function refreshPriceItem(record) {
    applyPriceItem(record);
    syncListRow(record);
    paintDetail();
  }

  function priceItemCodes(record) {
    return data.items
      .filter((item) => item.use === "사용" || item.code === record.code)
      .map((item) => item.code)
      .sort();
  }

  function nextPriceId() {
    const nums = data.prices.map((price) => Number(String(price.id).replace(/\D/g, ""))).filter((num) => !Number.isNaN(num));
    return "PR-" + String(Math.max(0, ...nums) + 1);
  }

  function isIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ""))) return false;
    const parsed = new Date(value + "T00:00:00");
    return !Number.isNaN(parsed.getTime()) && formatDate(parsed) === value;
  }

  function newVendor() {
    const current = selectedVendor();
    if (current && current.draft && !String(current.code || "").trim()) {
      const input = $("composite").querySelector('[data-field="code"]');
      if (input) input.focus();
      return;
    }
    const vendor = {
      tempId: "VNEW-" + vendorSeq++,
      code: "",
      name: "",
      bizNo: "",
      contact: "",
      phone: "",
      email: "",
      use: "사용",
      draft: true
    };
    data.vendors.unshift(vendor);
    state.filters = {};
    renderCriteria();
    state.selectedId = vendor.tempId;
    renderWorkspace();
    toast("협력사 등록을 열었습니다. 코드를 입력한 뒤 저장하세요.");
    const input = $("composite").querySelector('[data-field="code"]');
    if (input) input.focus();
  }

  function saveVendor() {
    const vendor = selectedVendor();
    if (!vendor) return;
    const code = normalizeItemCode(vendor.code);
    if (!code) {
      toast("협력사코드를 입력하세요.");
      return;
    }
    if (code.length > 20 || !/^[A-Z0-9]+(?:-[A-Z0-9]+)*$/.test(code)) {
      toast("협력사코드는 영문 대문자, 숫자, 하이픈만 20자 이내로 입력하세요.");
      return;
    }
    if (data.vendors.some((other) => other !== vendor && normalizeItemCode(other.code) === code)) {
      toast("이미 있는 협력사코드입니다.");
      return;
    }
    const name = String(vendor.name || "").trim();
    if (!name) {
      toast("협력사명을 입력하세요.");
      return;
    }
    if (data.vendors.some((other) => other !== vendor && other.name === name)) {
      toast("이미 있는 협력사명입니다.");
      return;
    }
    const bizNo = normalizeBizNo(vendor.bizNo);
    if (bizNo == null) {
      toast("사업자번호는 10자리 숫자로 입력하세요.");
      return;
    }
    if (bizNo && data.vendors.some((other) => other !== vendor && other.bizNo === bizNo)) {
      toast("이미 있는 사업자번호입니다.");
      return;
    }
    const email = String(vendor.email || "").trim();
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast("이메일 형식을 확인하세요.");
      return;
    }
    const creating = !!vendor.draft;
    const previous = vendor.savedName || "";
    vendor.code = code;
    vendor.name = name;
    vendor.bizNo = bizNo;
    vendor.contact = String(vendor.contact || "").trim();
    vendor.phone = String(vendor.phone || "").trim();
    vendor.email = email;
    if (!creating && previous && previous !== name) {
      data.orders.forEach((order) => {
        if (order.vendor === previous) order.vendor = name;
      });
      data.prices.forEach((price) => {
        if (price.vendor === previous) price.vendor = name;
      });
    }
    vendor.savedName = name;
    vendor.draft = false;
    delete vendor.tempId;
    state.selectedId = vendor.code;
    pushAudit(creating ? "등록" : "수정", vendor.code, previous, vendor.name, vendor.bizNo);
    paintList();
    paintDetail();
    toast(creating ? "협력사를 등록했습니다. 서버 저장은 아직 연결되지 않았습니다." : "협력사를 수정했습니다. 서버 저장은 아직 연결되지 않았습니다.");
  }

  function setVendorUse(next) {
    const vendor = selectedVendor();
    if (!vendor || vendor.draft) return;
    if (vendor.use === next) return;
    const before = vendor.use;
    vendor.use = next;
    pushAudit(next === "중지" ? "사용중지" : "사용재개", vendor.code, before, next, vendor.name);
    const stillVisible = filtered().some((row) => row.code === vendor.code);
    if (!stillVisible) {
      state.selectedId = firstId(filtered());
      paintList();
      paintDetail();
    } else {
      syncListRow(vendor);
      paintDetail();
    }
    toast(next === "중지" ? "사용 중지로 바꿨습니다. 기존 발주와 단가는 유지됩니다." : "사용으로 바꿨습니다.");
  }

  function normalizeBizNo(value) {
    const digits = String(value || "").replace(/\D/g, "");
    if (!digits) return "";
    if (digits.length !== 10) return null;
    return digits.slice(0, 3) + "-" + digits.slice(3, 5) + "-" + digits.slice(5);
  }

  function vendorNames(current) {
    const names = data.vendors
      .filter((vendor) => vendor.use === "사용" && vendor.name && !vendor.draft)
      .map((vendor) => vendor.name)
      .sort();
    if (current && !names.includes(current)) names.unshift(current);
    return names;
  }

  function newItem() {
    const current = selectedItem();
    if (current && current.draft && !String(current.code || "").trim()) {
      const input = $("composite").querySelector('[data-field="code"]');
      if (input) input.focus();
      return;
    }
    const item = {
      tempId: "NEW-" + itemSeq++,
      code: "",
      name: "",
      spec: "",
      unit: "EA",
      group: "원자재",
      use: "사용",
      draft: true
    };
    data.items.unshift(item);
    state.filters = {};
    renderCriteria();
    state.selectedId = item.tempId;
    renderWorkspace();
    toast("품목 등록을 열었습니다. 코드를 입력한 뒤 저장하세요.");
    const input = $("composite").querySelector('[data-field="code"]');
    if (input) input.focus();
  }

  function saveItem() {
    const item = selectedItem();
    if (!item) return;
    const code = normalizeItemCode(item.code);
    if (!code) {
      toast("품목코드를 입력하세요.");
      return;
    }
    if (code.length > 20 || !/^[A-Z0-9]+(?:-[A-Z0-9]+)*$/.test(code)) {
      toast("품목코드는 영문 대문자, 숫자, 하이픈만 20자 이내로 입력하세요.");
      return;
    }
    const duplicate = data.items.some((other) => other !== item && normalizeItemCode(other.code) === code);
    if (duplicate) {
      toast("이미 있는 품목코드입니다.");
      return;
    }
    const name = String(item.name || "").trim();
    if (!name) {
      toast("품명을 입력하세요.");
      return;
    }
    if (!item.unit) {
      toast("단위를 선택하세요.");
      return;
    }
    const creating = !!item.draft;
    item.code = code;
    item.name = name;
    item.spec = String(item.spec || "").trim();
    item.draft = false;
    delete item.tempId;
    state.selectedId = item.code;
    pushAudit(creating ? "등록" : "수정", item.code, "", item.name, item.spec);
    paintList();
    paintDetail();
    toast(creating ? "품목을 등록했습니다. 서버 저장은 아직 연결되지 않았습니다." : "품목을 수정했습니다. 서버 저장은 아직 연결되지 않았습니다.");
  }

  function setItemUse(next) {
    const item = selectedItem();
    if (!item || item.draft) return;
    const before = item.use;
    if (before === next) return;
    item.use = next;
    pushAudit(next === "중지" ? "사용중지" : "사용재개", item.code, before, next, "");
    const stillVisible = filtered().some((row) => row.code === item.code);
    if (!stillVisible) {
      state.selectedId = firstId(filtered());
      paintList();
      paintDetail();
    } else {
      syncListRow(item);
      paintDetail();
    }
    toast(next === "중지" ? "사용 중지로 바꿨습니다. 기존 발주와 단가는 유지됩니다." : "사용으로 바꿨습니다.");
  }

  function newOrder() {
    const order = {
      id: nextOrderId(),
      date: formatDate(new Date()),
      due: formatDate(new Date()),
      vendor: "",
      buyer: "김구매",
      status: "작성",
      currency: "KRW",
      vat: "별도",
      note: "",
      lines: [{ code: "", name: "", spec: "", unit: "EA", qty: 0, price: 0, due: formatDate(new Date()) }]
    };
    data.orders.unshift(order);
    state.filters = {};
    renderCriteria();
    state.selectedId = order.id;
    renderWorkspace();
    toast("작성 문서를 열었습니다.");
    const input = $("composite").querySelector('.detail-pane input[data-field="vendor"]');
    if (input) input.focus();
  }

  function confirmOrder() {
    const order = selectedOrder();
    if (!order.lines.some((line) => Number(line.qty) > 0 && line.code)) {
      toast("품목코드와 수량이 있는 행이 없습니다.");
      return;
    }
    order.status = "확정";
    pushAudit("확정", order.id, "작성", "확정", "");
    syncListRow(order);
    paintDetail();
    toast("화면에서 확정으로 표시했습니다.");
  }

  function cancelOrder() {
    const order = selectedOrder();
    order.status = "취소";
    pushAudit("취소", order.id, "확정", "취소", "");
    syncListRow(order);
    paintDetail();
    toast("화면에서 취소로 표시했습니다.");
  }

  function requestPrice() {
    const price = selectedPrice();
    const next = Number(String(price.request).replace(/,/g, ""));
    if (!next || next === Number(price.price)) {
      toast("현재단가와 다른 요청단가를 입력하세요.");
      return;
    }
    price.status = "승인대기";
    price.history.unshift({
      date: formatDate(new Date()),
      type: "변경요청",
      before: price.price,
      after: next,
      by: "김구매",
      note: ""
    });
    pushAudit("변경요청", price.code, money(price.price), money(next), "");
    syncListRow(price);
    paintDetail();
    toast("변경 요청을 승인 대기로 표시했습니다.");
  }

  function decidePrice(type) {
    const price = selectedPrice();
    const pending = price.history.find((row) => row.type === "변경요청");
    const after = pending ? pending.after : Number(price.request);
    if (type === "승인") {
      price.history.unshift({ date: formatDate(new Date()), type: "승인", before: price.price, after: after, by: "김구매", note: "" });
      price.price = after;
      price.request = "";
      price.status = "적용중";
    } else {
      price.history.unshift({ date: formatDate(new Date()), type: "반려", before: price.price, after: after, by: "김구매", note: "" });
      price.request = "";
      price.status = "적용중";
    }
    pushAudit(type, price.code, money(price.history[0].before), money(after), "");
    syncListRow(price);
    paintDetail();
    toast(type === "승인" ? "화면에서 단가를 승인했습니다." : "화면에서 요청을 반려했습니다.");
  }

  function pushAudit(action, target, before, after, note) {
    data.audit.unshift({
      at: formatDate(new Date()) + " " + formatTime(new Date()),
      user: "김구매",
      action: action,
      target: target,
      before: before,
      after: after,
      note: note
    });
  }

  function filtered() {
    const filters = state.filters;
    if (state.module === "orders") {
      return data.orders.filter((order) => {
        if (filters.from && order.date < filters.from) return false;
        if (filters.to && order.date > filters.to) return false;
        if (filters.status && filters.status !== "전체" && order.status !== filters.status) return false;
        if (filters.vendor && !order.vendor.includes(filters.vendor)) return false;
        if (filters.q && !orderBlob(order).includes(filters.q.toLowerCase())) return false;
        return true;
      });
    }
    if (state.module === "prices") {
      return data.prices.filter((price) => {
        if (filters.status && filters.status !== "전체" && price.status !== filters.status) return false;
        if (filters.vendor && !price.vendor.includes(filters.vendor)) return false;
        if (filters.q && !(price.code + price.name + price.spec).toLowerCase().includes(filters.q.toLowerCase())) return false;
        return true;
      });
    }
    if (state.module === "items") {
      return data.items.filter((item) => {
        if (filters.use && filters.use !== "전체" && item.use !== filters.use) return false;
        if (filters.group && filters.group !== "전체" && item.group !== filters.group) return false;
        if (filters.q && !(item.code + item.name + item.spec).toLowerCase().includes(filters.q.toLowerCase())) return false;
        return true;
      });
    }
    if (state.module === "vendors") {
      return data.vendors.filter((vendor) => {
        if (filters.use && filters.use !== "전체" && vendor.use !== filters.use) return false;
        if (filters.q && !(vendor.code + vendor.name + vendor.contact).toLowerCase().includes(filters.q.toLowerCase())) return false;
        return true;
      });
    }
    return data.audit.filter((row) => {
      if (filters.action && filters.action !== "전체" && row.action !== filters.action) return false;
      if (filters.q && !(row.user + row.target + row.note + row.action).toLowerCase().includes(filters.q.toLowerCase())) return false;
      return true;
    });
  }

  function sortRows(rows) {
    const key = state.sortKey;
    const dir = state.sortDir === "asc" ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const av = sortValue(a, key);
      const bv = sortValue(b, key);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }

  function sortValue(row, key) {
    if (key === "amount") return orderAmount(row);
    const value = row[key];
    if (typeof value === "number") return value;
    return value == null ? "" : String(value);
  }

  function syncListRow(record) {
    const tr = $("composite").querySelector('tr[data-id="' + cssEscape(rowId(record)) + '"]');
    if (!tr) return;
    const cells = tr.children;
    if (state.module === "orders") {
      cells[1].textContent = record.date;
      cells[2].textContent = record.vendor;
      cells[3].replaceChildren(stateNode(record.status));
      cells[4].textContent = money(orderAmount(record));
    } else if (state.module === "prices") {
      cells[0].textContent = record.code;
      cells[1].textContent = record.name;
      cells[2].textContent = record.vendor;
      cells[3].textContent = money(record.price);
      cells[4].textContent = record.from;
      cells[5].replaceChildren(stateNode(record.status));
    } else if (state.module === "items") {
      cells[0].textContent = record.code;
      cells[1].textContent = record.name;
      cells[2].textContent = record.spec;
      cells[3].textContent = record.unit;
      cells[4].textContent = record.group;
      cells[5].replaceChildren(stateNode(record.use));
    } else if (state.module === "vendors") {
      cells[0].textContent = record.code;
      cells[1].textContent = record.name;
      cells[2].textContent = record.bizNo;
      cells[3].textContent = record.contact;
      cells[4].textContent = record.phone;
      cells[5].replaceChildren(stateNode(record.use));
    }
  }

  function updateOrderFoot(lines, record) {
    const qtyCell = lines.querySelector('[data-foot="qty"]');
    const amountCell = lines.querySelector('[data-foot="amount"]');
    if (qtyCell) qtyCell.textContent = qty(record.lines.reduce((sum, line) => sum + Number(line.qty || 0), 0));
    if (amountCell) amountCell.textContent = money(orderAmount(record));
  }

  function paintTab() {
    const tab = $("doc-tab");
    const record = selectedRecord();
    let text = TITLES[state.module];
    if (record && state.module === "orders") text = record.id + " 발주";
    else if (record && state.module === "prices") text = record.code + " 단가";
    else if (record && state.module === "items") text = (record.code || "신규") + " 품목";
    else if (record && state.module === "vendors") text = (record.code || "신규") + " 협력사";
    else if (state.module === "audit") text = "변경 이력";
    tab.replaceChildren(el("span", {}, text));
  }

  function renderStatus() {
    const rows = filtered();
    const record = selectedRecord();
    let left = rows.length + "건";
    if (record && state.module === "orders") left += "  ·  " + record.id + "  ·  공급가액 " + money(orderAmount(record));
    else if (record && state.module === "prices") left += "  ·  " + record.code + "  ·  " + money(record.price);
    else if (record && state.module === "items") left += "  ·  " + (record.code || "신규");
    else if (record && state.module === "vendors") left += "  ·  " + (record.code || "신규") + "  ·  " + (record.name || "");
    $("statusbar").replaceChildren(
      el("span", {}, left),
      el("span", { class: "msg" }, state.message),
      el("span", { class: "hint" }, state.api + "  ·  ↑↓ 행 이동")
    );
  }

  function printCurrent() {
    const root = $("print-root");
    root.replaceChildren();
    if (state.module === "orders" && selectedOrder()) printOrder(root, selectedOrder());
    else printTable(root, TITLES[state.module], listColumns(), sortRows(filtered()));
    window.print();
  }

  function printOrder(root, order) {
    root.append(el("h1", {}, "발주서"));
    root.append(el("div", { class: "print-meta" }, el("span", {}, "구매사 (주)한성산업"), el("span", {}, order.id)));
    const head = el("table");
    head.append(printRow(["문서번호", order.id, "상태", order.status, "발주일", order.date, "납기일", order.due]));
    head.append(printRow(["협력사", order.vendor, "담당", order.buyer, "통화", order.currency, "부가세", order.vat]));
    head.append(printRow(["비고", order.note || " ", "", "", "", "", "", ""]));
    const lines = el("table");
    lines.append(el("tr", {}, ["No", "품목코드", "품목명", "규격", "단위", "수량", "단가", "공급가액", "납기"].map((label, index) => {
      return el("th", { class: index >= 5 && index <= 7 ? "num" : "" }, label);
    })));
    order.lines.forEach((line, index) => {
      lines.append(el("tr", {}, [
        el("td", { class: "num" }, String(index + 1)),
        el("td", {}, line.code),
        el("td", {}, line.name),
        el("td", {}, line.spec),
        el("td", {}, line.unit),
        el("td", { class: "num" }, qty(line.qty)),
        el("td", { class: "num" }, money(line.price)),
        el("td", { class: "num" }, money(lineAmount(line))),
        el("td", {}, line.due)
      ]));
    });
    lines.append(el("tr", {}, [
      el("td", { colspan: "5" }, "합계"),
      el("td", { class: "num" }, qty(order.lines.reduce((sum, line) => sum + Number(line.qty || 0), 0))),
      el("td", {}, ""),
      el("td", { class: "num" }, money(orderAmount(order))),
      el("td", {}, "")
    ]));
    const sign = el("div", { class: "print-sign" }, el("div", {}, "담당"), el("div", {}, "승인"));
    root.append(head, lines, sign, el("p", { class: "print-note" }, "부가세 별도. 직인과 양식은 출력 견본이 확정되기 전의 기본 배치입니다."));
  }

  function printTable(root, title, columns, rows) {
    root.append(el("h1", {}, title));
    root.append(el("div", { class: "print-meta" }, el("span", {}, "구매사 (주)한성산업"), el("span", {}, rows.length + "건")));
    const table = el("table");
    table.append(el("tr", {}, columns.map((column) => el("th", { class: column.align === "num" ? "num" : "" }, column.label))));
    rows.forEach((row, index) => {
      table.append(el("tr", {}, columns.map((column) => {
        const value = column.render ? column.render(row, index) : row[column.key];
        const text = value && value.nodeType ? value.textContent : (value == null ? "" : String(value));
        return el("td", { class: column.align === "num" ? "num" : "" }, text);
      })));
    });
    root.append(table);
  }

  function printRow(values) {
    return el("tr", {}, values.map((value) => el("td", {}, value)));
  }

  function wireSplitter(splitter, list) {
    splitter.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      splitter.classList.add("is-drag");
      const parent = splitter.parentElement;
      const move = (ev) => {
        const rect = parent.getBoundingClientRect();
        const percent = ((ev.clientX - rect.left) / rect.width) * 100;
        state.split = Math.max(28, Math.min(62, percent));
        list.style.flexBasis = state.split + "%";
      };
      const stop = () => {
        splitter.classList.remove("is-drag");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
    });
  }

  function pane(className, title, capId) {
    const node = el("section", { class: "pane " + className });
    const cap = el("div", { class: "pane-cap", id: capId }, el("span", { class: "cap-title" }, el("i"), title), el("span", { class: "cap-meta" }, ""));
    node.append(cap);
    if (className === "detail-pane") {
      node.append(el("div", { class: "form" }));
      node.append(el("div", { class: "pane-cap detail-lines", id: capId + "-lines" }, el("span", { class: "cap-title" }, el("i"), lineCaption()), el("span", { class: "cap-meta" }, "")));
      node.append(el("div", { class: "grid-scroll line-scroll", tabindex: "0" }));
    } else {
      node.append(el("div", { class: "grid-scroll", tabindex: "0", "aria-labelledby": capId }));
    }
    return node;
  }

  function field(label, ...controls) {
    return el("label", { class: "field" }, el("span", {}, label), ...controls);
  }
  function dateInput(key, value) {
    return el("input", { type: "date", "data-filter": key, value: value });
  }
  function textInput(key, className, value) {
    return el("input", { type: "text", class: className, "data-filter": key, value: value });
  }
  function searchInput(key, placeholder) {
    return el("input", { type: "search", "data-filter": key, placeholder: placeholder, value: "" });
  }
  function select(key, options, value) {
    const node = el("select", { "data-filter": key });
    options.forEach((option) => node.append(el("option", { value: option, selected: option === value ? "selected" : null }, option)));
    return node;
  }
  function lineCell(row, index, key, edit, numeric) {
    if (!edit) return numeric ? (key === "qty" ? qty(row[key]) : money(row[key])) : show(row[key]);
    return el("input", {
      class: "cell-input",
      "data-index": String(index),
      "data-key": key,
      value: row[key] == null ? "" : String(row[key])
    });
  }
  function stateNode(value) {
    return el("span", { class: "state " + stateClass(value) }, value || "");
  }
  function stateClass(value) {
    if (["확정", "적용중", "승인", "사용", "등록"].includes(value)) return "ok";
    if (["승인대기", "변경요청"].includes(value)) return "wait";
    if (["취소", "반려", "중지"].includes(value)) return "stop";
    if (["종료"].includes(value)) return "mute";
    return "";
  }
  function canEdit(record) {
    if (state.module === "orders") return record.status === "작성";
    if (state.module === "prices") return !!record.draft || record.status === "적용중";
    if (state.module === "items") return true;
    if (state.module === "vendors") return true;
    return false;
  }
  function selectedRecord() {
    if (state.module === "orders") return selectedOrder();
    if (state.module === "prices") return selectedPrice();
    if (state.module === "items") return selectedItem();
    if (state.module === "vendors") return selectedVendor();
    return null;
  }
  function selectedVendor() {
    return data.vendors.find((vendor) => (vendor.draft ? vendor.tempId : vendor.code) === state.selectedId) || null;
  }
  function selectedItem() {
    return data.items.find((item) => (item.draft ? item.tempId : item.code) === state.selectedId) || null;
  }
  function normalizeItemCode(value) {
    return String(value || "").trim().toUpperCase();
  }
  function fieldSelect(record, field) {
    const node = el("select", { "data-field": field.key });
    const options = field.allowEmpty ? [""].concat(field.options) : field.options.slice();
    options.forEach((option) => {
      const label = option === "" ? "선택" : option;
      node.append(el("option", { value: option, selected: option === (record[field.key] || "") ? "selected" : null }, label));
    });
    node.addEventListener("change", () => {
      record[field.key] = node.value;
      if (typeof field.after === "function") field.after(record);
      syncListRow(record);
      renderStatus();
    });
    return node;
  }
  function fieldInputAttrs(record, field, editable) {
    const attrs = {
      value: editable && field.date ? show(record[field.key]) : fieldText(record, field, editable),
      readonly: editable ? null : "readonly",
      "data-field": field.key
    };
    if (editable && field.date) attrs.type = "date";
    if (editable && field.money) attrs.inputMode = "decimal";
    return attrs;
  }
  function selectedOrder() { return data.orders.find((order) => order.id === state.selectedId) || null; }
  function selectedPrice() { return data.prices.find((price) => price.id === state.selectedId) || null; }
  function lineRecords(record) {
    if (state.module === "orders") return record.lines;
    if (state.module === "prices") return record.history;
    if (state.module === "vendors") return data.prices.filter((price) => price.vendor === record.name && !price.draft);
    return contractsFor(record.code);
  }
  function contractsFor(code) { return data.prices.filter((price) => price.code === code); }
  function rowId(row) {
    if (state.module === "orders") return row.id;
    if (state.module === "prices") return row.id;
    if (state.module === "items") return row.draft ? row.tempId : row.code;
    if (state.module === "vendors") return row.draft ? row.tempId : row.code;
    return row.at + row.target;
  }
  function firstId(rows) { return rows.length ? rowId(rows[0]) : ""; }
  function orderAmount(order) { return order.lines.reduce((sum, line) => sum + lineAmount(line), 0); }
  function lineAmount(line) { return Math.round(Number(line.qty || 0) * Number(line.price || 0)); }
  function orderBlob(order) {
    return (order.id + order.vendor + order.lines.map((line) => line.code + line.name).join("")).toLowerCase();
  }
  function nextOrderId() {
    const nums = data.orders.map((order) => Number(order.id.slice(-4))).filter((num) => !Number.isNaN(num));
    return "PO-202611-" + String(Math.max(0, ...nums) + 1).padStart(4, "0");
  }
  function listCaption() {
    return { orders: "발주 목록", prices: "계약 단가", items: "품목", vendors: "협력사" }[state.module];
  }
  function detailCaption() {
    return { orders: "발주 정보", prices: "단가 정보", items: "품목 정보", vendors: "협력사 정보" }[state.module];
  }
  function lineCaption() {
    return { orders: "품목", prices: "단가 이력", items: "계약 단가", vendors: "계약 단가" }[state.module];
  }
  function apiBase() {
    const configured = window.SCM_CONFIG && window.SCM_CONFIG.apiBase;
    if (configured && String(configured).trim()) return String(configured).trim().replace(/\/$/, "");
    const host = location.hostname;
    if (host === "localhost" || host === "127.0.0.1") return "http://127.0.0.1:8000";
    return "";
  }

  function checkApi() {
    const base = apiBase();
    if (!base) {
      state.api = "API 주소 없음";
      renderStatus();
      return;
    }
    fetch(base + "/health")
      .then((response) => {
        state.api = response.ok ? "API 연결" : "API 응답 오류";
        renderStatus();
      })
      .catch(() => {
        state.api = "API 연결 안 됨";
        renderStatus();
      });
  }

  function countText(count) { return count + "건을 조회했습니다."; }
  function toast(message) {
    state.message = message;
    renderStatus();
    clearTimeout(state.timer);
    state.timer = setTimeout(() => {
      state.message = "";
      renderStatus();
    }, 4000);
  }
  function money(value) {
    if (value === "" || value == null || Number.isNaN(Number(value))) return "";
    return Math.round(Number(value)).toLocaleString("ko-KR");
  }
  function qty(value) {
    return Number(value || 0).toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  }
  function fieldText(record, field, editable) {
    let value = record[field.key];
    if (field.key === "unit" && state.module === "prices" && (value == null || value === "")) {
      const item = data.items.find((row) => row.code === record.code);
      value = item ? item.unit : "";
    }
    if ((value == null || value === "") && field.key === "to" && !editable) return "—";
    if (field.money && !editable && value !== "" && value != null) return money(value);
    return show(value);
  }
  function show(value) { return value == null ? "" : String(value); }
  function formatDate(date) {
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + month + "-" + day;
  }
  function formatTime(date) {
    return String(date.getHours()).padStart(2, "0") + ":" + String(date.getMinutes()).padStart(2, "0");
  }
  function cssEscape(value) {
    return window.CSS && CSS.escape ? CSS.escape(value) : value.replace(/"/g, '\\"');
  }
  function el(tag, attrs) {
    const node = document.createElement(tag);
    const children = Array.prototype.slice.call(arguments, 2);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value == null) return;
      if (key === "class") node.className = value;
      else if (key === "onclick" || key === "onkeydown") node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    });
    children.flat().forEach((child) => {
      if (child == null || child === "") return;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    });
    return node;
  }
})();
