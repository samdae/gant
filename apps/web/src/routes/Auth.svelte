<script lang="ts">
  import { setToken } from "../stores/auth";

  let tokenInput = "";
  let error = "";

  const getReturnPath = () => {
    const hash = window.location.hash;
    const queryIndex = hash.indexOf("?");
    if (queryIndex === -1) return "#/";
    const query = hash.slice(queryIndex + 1);
    const params = new URLSearchParams(query);
    const returnTo = params.get("return");
    return returnTo?.startsWith("#/") ? returnTo : "#/";
  };

  const save = () => {
    if (!tokenInput.trim()) {
      error = "토큰을 입력해 주세요.";
      return;
    }
    setToken(tokenInput.trim());
    window.location.hash = getReturnPath();
  };

  const cancel = () => {
    window.location.hash = "#/";
  };
</script>

<section class="page" id="page-auth">
  <div class="page-container" style="max-width:420px">
    <form class="card" style="padding:22px" on:submit|preventDefault={save}>
      <div class="page-header" style="margin-bottom:12px">
        <h2>관리자 접근</h2>
      </div>

      <label class="form-label" for="tokenInput">관리자 토큰</label>
      <input id="tokenInput" type="password" autocomplete="off" aria-invalid={Boolean(error)} aria-describedby={error ? "token-error" : undefined} class="input" bind:value={tokenInput} />
      {#if error}
        <div id="token-error" role="alert" class="error-text" style="margin-top:10px">{error}</div>
      {/if}

      <div class="modal-footer" style="justify-content:flex-end;margin-top:16px">
        <button type="button" class="btn btn-ghost" on:click={cancel}>취소</button>
        <button type="submit" class="btn btn-primary">저장</button>
      </div>
    </form>
  </div>
</section>
