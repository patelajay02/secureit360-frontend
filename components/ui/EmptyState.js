// components/ui/EmptyState.js
// SecureIT360 — Empty state component
// Shows friendly message when no data exists yet

export function EmptyState({ 
  icon = "🔍", 
  title, 
  description, 
  buttonText, 
  onButtonClick 
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="text-5xl mb-4">{icon}</div>
      <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
      <p className="text-gray-400 text-sm max-w-sm mb-6">{description}</p>
      {buttonText && onButtonClick && (
        <button
          onClick={onButtonClick}
          className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-3 rounded-lg transition-colors"
        >
          {buttonText}
        </button>
      )}
    </div>
  );
}

export function NoScansYet({ onStartScan }) {
  return (
    <EmptyState
      icon="🛡️"
      title="No scans run yet"
      description="Run your first security scan to see your Ransom Risk Score and find out exactly where your business is vulnerable."
      buttonText="Start my first scan"
      onButtonClick={onStartScan}
    />
  );
}

export function NoFindingsYet() {
  return (
    <EmptyState
      icon="✅"
      title="No issues found"
      description="Your last scan found no security issues. We will keep scanning every day and alert you if anything changes."
    />
  );
}

export function NoDomainsYet({ onAddDomain }) {
  return (
    <EmptyState
      icon="🌐"
      title="No domains added yet"
      description="Add your company domain to start scanning for security risks."
      buttonText="Add my domain"
      onButtonClick={onAddDomain}
    />
  );
}

export function NoTeamMembersYet({ onInvite }) {
  return (
    <EmptyState
      icon="👥"
      title="No team members yet"
      description="Invite your team to give them access to your security dashboard."
      buttonText="Invite a team member"
      onButtonClick={onInvite}
    />
  );
}