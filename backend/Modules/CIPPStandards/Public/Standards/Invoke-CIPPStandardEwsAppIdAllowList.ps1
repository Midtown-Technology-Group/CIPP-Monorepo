function Invoke-CIPPStandardEwsAppIdAllowList {
    <#
    .FUNCTIONALITY
        Internal
    .COMPONENT
        (APIName) EwsAppIdAllowList
    .SYNOPSIS
        (Label) Configure EWS application ID allow list
    .DESCRIPTION
        (Helptext) Keeps Exchange Web Services temporarily enabled only for the specified Entra application IDs during Microsoft's EWS retirement. Enter every application ID that the tenant still requires. This standard replaces the complete allow list and must not be combined with the Disable Exchange Web Services standard.
        (DocsDescription) Sets EwsEnabled to true and configures the complete EwsAllowedAppIDs list in Exchange Online. Only the listed Entra applications can use EWS. Use this as a temporary migration control for tenants with verified EWS dependencies, and remove applications as vendors migrate to Microsoft Graph or other supported APIs. The standard validates every value as an application ID, compares lists without regard to order, and refuses an empty list. Do not enable this standard together with Disable Exchange Web Services.
    .NOTES
        CAT
            Exchange Standards
        TAG
        EXECUTIVETEXT
            Restricts temporary Exchange Web Services access to explicitly approved business applications while legacy integrations are migrated before EWS retirement.
        ADDEDCOMPONENT
            {"type":"autoComplete","multiple":true,"creatable":true,"required":true,"label":"Allowed Entra application IDs","name":"standards.EwsAppIdAllowList.AllowedAppIds"}
        IMPACT
            High Impact
        ADDEDDATE
            2026-09-16
        POWERSHELLEQUIVALENT
            Set-OrganizationConfig -EwsEnabled \$true -EwsAllowedAppIDs "<comma-separated application IDs>"
        RECOMMENDEDBY
        REQUIREDCAPABILITIES
            "EXCHANGE_S_STANDARD"
            "EXCHANGE_S_ENTERPRISE"
            "EXCHANGE_S_STANDARD_GOV"
            "EXCHANGE_S_ENTERPRISE_GOV"
            "EXCHANGE_LITE"
        UPDATECOMMENTBLOCK
            Run the Tools\Update-StandardsComments.ps1 script to update this comment block
    .LINK
        https://docs.cipp.app/user-documentation/tenant/standards/alignment/templates/available-standards
    #>

    param($Tenant, $Settings)

    $TestResult = Test-CIPPStandardLicense -StandardName 'EwsAppIdAllowList' -TenantFilter $Tenant -Preset Exchange
    if ($TestResult -eq $false) {
        return $true
    }

    $RawAllowedAppIds = @($Settings.AllowedAppIds | ForEach-Object { $_.value ?? $_ })
    $DesiredAppIds = @(
        $RawAllowedAppIds |
            ForEach-Object { $_ -split ',' } |
            ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Sort-Object -Unique
    )

    $InvalidAppIds = @($DesiredAppIds | Where-Object {
            $ParsedGuid = [guid]::Empty
            -not [guid]::TryParse($_, [ref]$ParsedGuid)
        })

    if ($DesiredAppIds.Count -eq 0 -or $InvalidAppIds.Count -gt 0) {
        $Reason = if ($DesiredAppIds.Count -eq 0) {
            'At least one allowed Entra application ID is required.'
        } else {
            "Invalid Entra application ID value(s): $($InvalidAppIds -join ', ')."
        }
        Write-LogMessage -API 'Standards' -Tenant $Tenant -Message "EwsAppIdAllowList: $Reason" -Sev Error
        return
    }

    function Get-NormalizedEwsAppIdList {
        param($Value)

        return @(
            @($Value) |
                ForEach-Object { $_ -split ',' } |
                ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                Sort-Object -Unique
        )
    }

    try {
        $CurrentConfig = New-ExoRequest -tenantid $Tenant -cmdlet 'Get-OrganizationConfig' -cmdParams @{ RetrieveEwsOperationAccessPolicy = $true }
    } catch {
        $ErrorMessage = Get-NormalizedError -Message $_.Exception.Message
        Write-LogMessage -API 'Standards' -Tenant $Tenant -Message "Failed to retrieve the EWS application ID policy: $ErrorMessage" -Sev Error
        return
    }

    $CurrentAppIds = Get-NormalizedEwsAppIdList -Value $CurrentConfig.EwsAllowedAppIDs
    $CurrentEnabled = $CurrentConfig.EwsEnabled
    $ListsMatch = ($DesiredAppIds -join ',') -eq ($CurrentAppIds -join ',')
    $StateIsCorrect = $CurrentEnabled -eq $true -and $ListsMatch

    if ($Settings.remediate -eq $true) {
        if ($StateIsCorrect) {
            Write-LogMessage -API 'Standards' -Tenant $Tenant -Message 'EWS is already enabled with the required application ID allow list.' -Sev Info
        } else {
            try {
                $null = New-ExoRequest -tenantid $Tenant -cmdlet 'Set-OrganizationConfig' -cmdParams @{
                    EwsEnabled       = $true
                    EwsAllowedAppIDs = $DesiredAppIds -join ','
                } -UseSystemMailbox $true

                $CurrentConfig = New-ExoRequest -tenantid $Tenant -cmdlet 'Get-OrganizationConfig' -cmdParams @{ RetrieveEwsOperationAccessPolicy = $true }
                $CurrentAppIds = Get-NormalizedEwsAppIdList -Value $CurrentConfig.EwsAllowedAppIDs
                $CurrentEnabled = $CurrentConfig.EwsEnabled
                $ListsMatch = ($DesiredAppIds -join ',') -eq ($CurrentAppIds -join ',')
                $StateIsCorrect = $CurrentEnabled -eq $true -and $ListsMatch

                if (-not $StateIsCorrect) {
                    throw 'Exchange Online readback did not match the requested EWS application ID policy.'
                }

                Write-LogMessage -API 'Standards' -Tenant $Tenant -Message "Enabled EWS with $($DesiredAppIds.Count) allowed application ID(s)." -Sev Info
            } catch {
                $ErrorMessage = Get-NormalizedError -Message $_.Exception.Message
                Write-LogMessage -API 'Standards' -Tenant $Tenant -Message "Failed to configure the EWS application ID allow list: $ErrorMessage" -Sev Error
            }
        }
    }

    if ($Settings.alert -eq $true) {
        if ($StateIsCorrect) {
            Write-LogMessage -API 'Standards' -Tenant $Tenant -Message 'The EWS application ID allow list is configured as required.' -Sev Info
        } else {
            $AlertObject = [PSCustomObject]@{
                EwsEnabled       = $CurrentEnabled
                EwsAllowedAppIDs = $CurrentAppIds
                RequiredAppIDs   = $DesiredAppIds
            }
            Write-StandardsAlert -message 'The EWS enabled state or application ID allow list does not match the required configuration.' -object $AlertObject -tenant $Tenant -standardName 'EwsAppIdAllowList' -standardId $Settings.standardId
        }
    }

    if ($Settings.report -eq $true) {
        $CurrentValue = [PSCustomObject]@{
            EwsEnabled       = $CurrentEnabled
            EwsAllowedAppIDs = $CurrentAppIds
        }
        $ExpectedValue = [PSCustomObject]@{
            EwsEnabled       = $true
            EwsAllowedAppIDs = $DesiredAppIds
        }
        Set-CIPPStandardsCompareField -FieldName 'standards.EwsAppIdAllowList' -CurrentValue $CurrentValue -ExpectedValue $ExpectedValue -TenantFilter $Tenant
        Add-CIPPBPAField -FieldName 'EwsAppIdAllowList' -FieldValue $StateIsCorrect -StoreAs bool -Tenant $Tenant
    }
}
