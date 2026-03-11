<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Analyzer - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-dark d-flex align-items-center justify-content-center" style="min-height:100vh">
<div class="card" style="width:24rem">
    <div class="card-body">
        <h5 class="card-title mb-3">Stock Analyzer</h5>
        <form method="get" action="<?= BASE_URL ?>/">
            <div class="mb-3">
                <label for="token" class="form-label">Access Token</label>
                <input type="password" class="form-control" id="token" name="token" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Enter</button>
        </form>
    </div>
</div>
</body>
</html>
